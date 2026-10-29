package com.tracelink.app

import android.content.Context
import android.os.Handler
import android.os.Looper
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.security.SecureRandom
import java.time.Instant
import kotlin.concurrent.thread

private fun hasAll(context: Context, perms: Array<String>) = perms.all {
    context.checkSelfPermission(it) == android.content.pm.PackageManager.PERMISSION_GRANTED
}

private fun newNonce(): String {
    val b = ByteArray(12)
    SecureRandom().nextBytes(b)
    return b.joinToString("") { "%02x".format(it) }
}

/** Broadcast mode: this phone sends its rotating ID so a finder can recognise it. */
@Composable
fun BroadcastScreen(api: Api, device: Device, onBack: () -> Unit) {
    val context = LocalContext.current
    val view = LocalView.current
    val prefs = remember { context.getSharedPreferences("tracelink", Context.MODE_PRIVATE) }
    var status by remember { mutableStateOf("Not started") }
    var error by remember { mutableStateOf<String?>(null) }
    var on by remember { mutableStateOf(false) }
    var shownId by remember { mutableStateOf("") }
    val main = remember { Handler(Looper.getMainLooper()) }
    val broadcaster = remember { Broadcaster(context) { s -> main.post { status = s } } }
    val perms = remember { bluetoothPermissions(finder = false) }

    DisposableEffect(Unit) {
        view.keepScreenOn = true
        onDispose {
            view.keepScreenOn = false
            broadcaster.stop()
        }
    }

    fun begin() {
        error = null
        thread {
            try {
                // Cached so the phone can keep broadcasting; the server hands out the same secret again anyway.
                val key = "secret_${device.id}"
                val cached = prefs.getString(key, null)
                val secret = if (cached != null) {
                    java.util.Base64.getUrlDecoder().decode(cached)
                } else {
                    api.enroll(device.id).also {
                        prefs.edit().putString(key, java.util.Base64.getUrlEncoder().encodeToString(it)).apply()
                    }
                }
                main.post {
                    broadcaster.start(secret)
                    on = true
                    // Show the ID once it has been computed.
                    main.postDelayed({ shownId = broadcaster.currentId }, 800)
                }
            } catch (e: ApiException) {
                main.post { error = e.message }
            } catch (e: Exception) {
                main.post { error = "Could not start: ${e.message}" }
            }
        }
    }

    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { granted ->
        if (granted.values.all { it }) begin() else error = "Bluetooth permission is needed to broadcast."
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Spacer(Modifier.height(24.dp))
        Text("Broadcast", fontSize = 28.sp, fontWeight = FontWeight.ExtraBold)
        Text(device.nickname, fontSize = 20.sp)
        Text(
            "This phone sends a short ID over Bluetooth that changes every 15 minutes, so nobody can follow it. " +
                "A finder's report only counts if you have opened a lost-phone case for this device on the website."
        )
        Text("Status: $status", fontWeight = FontWeight.Bold)
        if (shownId.isNotEmpty() && on) Text("Current ID: $shownId", fontFamily = FontFamily.Monospace)
        if (error != null) Text(error!!, color = MaterialTheme.colorScheme.error)
        Text("Keep this screen open while testing. Android may stop Bluetooth in the background; a real release would use a foreground service.")
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            if (!on) {
                Button(onClick = {
                    if (perms.isEmpty() || hasAll(context, perms)) begin() else launcher.launch(perms)
                }) { Text("Start broadcasting") }
            } else {
                Button(onClick = { broadcaster.stop(); on = false; shownId = "" }) { Text("Stop") }
            }
            OutlinedButton(onClick = onBack) { Text("Back") }
        }
    }
}

/** Finder mode: listens for TraceLink beacons and reports where it heard them. */
@Composable
fun FinderScreen(api: Api, onBack: () -> Unit) {
    val context = LocalContext.current
    val view = LocalView.current
    var status by remember { mutableStateOf("Not started") }
    var error by remember { mutableStateOf<String?>(null) }
    var on by remember { mutableStateOf(false) }
    var heard by remember { mutableIntStateOf(0) }
    var sent by remember { mutableIntStateOf(0) }
    var last by remember { mutableStateOf("Nothing heard yet") }
    var gps by remember { mutableStateOf("No position yet") }
    val main = remember { Handler(Looper.getMainLooper()) }
    val tracker = remember { LocationTracker(context) }
    val lastSent = remember { HashMap<String, Long>() }
    val perms = remember { bluetoothPermissions(finder = true) }

    val finder = remember {
        Finder(
            context,
            onHeard = { id, rssi ->
                main.post {
                    heard += 1
                    val now = System.currentTimeMillis()
                    val fix = tracker.fresh()
                    if (fix == null) {
                        last = "Heard a beacon (signal $rssi dBm) but there is no fresh GPS position, so nothing was sent."
                        return@post
                    }
                    // At most one report per beacon per minute, so a phone sitting next to you does not flood the server.
                    if (now - (lastSent[id] ?: 0L) < 60_000) return@post
                    lastSent[id] = now
                    val observedAt = Instant.ofEpochMilli(now).toString()
                    val acc = fix.accuracy.toDouble().coerceIn(0.0, 100000.0)
                    thread {
                        try {
                            api.report(id, observedAt, fix.latitude, fix.longitude, acc, newNonce())
                            main.post {
                                sent += 1
                                last = "Reported a beacon (signal $rssi dBm), position accurate to ${acc.toInt()} m"
                            }
                        } catch (e: ApiException) {
                            main.post { last = "Report failed: ${e.message}" }
                        }
                    }
                }
            },
            onStatus = { s -> main.post { status = s } },
        )
    }

    DisposableEffect(Unit) {
        view.keepScreenOn = true
        val refresh = object : Runnable {
            override fun run() {
                val f = tracker.fresh()
                gps = if (f == null) "No fresh position" else "Position accurate to ${f.accuracy.toInt()} m"
                main.postDelayed(this, 2000)
            }
        }
        main.post(refresh)
        onDispose {
            view.keepScreenOn = false
            main.removeCallbacks(refresh)
            finder.stop()
            try { tracker.stop() } catch (_: Exception) {}
        }
    }

    fun begin() {
        error = null
        if (!tracker.enabled()) {
            error = "Turn on Location in the phone settings, then try again."
            return
        }
        tracker.start()
        finder.start()
        on = true
    }

    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { granted ->
        if (granted.values.all { it }) begin() else error = "Bluetooth and location permission are needed to scan."
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Spacer(Modifier.height(24.dp))
        Text("Finder mode", fontSize = 28.sp, fontWeight = FontWeight.ExtraBold)
        Text(
            "While this is on, the phone listens for TraceLink beacons and sends the beacon ID with this phone's GPS position and the time. " +
                "The server keeps a report only if it matches a phone whose owner opened a lost-phone case. This phone never learns whose it is."
        )
        Text("Status: $status", fontWeight = FontWeight.Bold)
        Text(gps)
        Text("Signals heard: $heard   Reports sent: $sent")
        Text(last)
        if (error != null) Text(error!!, color = MaterialTheme.colorScheme.error)
        Text("Keep this screen open. Test only with phones you own.")
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            if (!on) {
                Button(onClick = {
                    if (hasAll(context, perms)) begin() else launcher.launch(perms)
                }) { Text("Start scanning") }
            } else {
                Button(onClick = { finder.stop(); tracker.stop(); on = false }) { Text("Stop") }
            }
            OutlinedButton(onClick = onBack) { Text("Back") }
        }
    }
}
