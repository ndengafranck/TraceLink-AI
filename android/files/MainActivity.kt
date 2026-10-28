package com.tracelink.app

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.concurrent.thread

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(Modifier.fillMaxSize()) { App() }
            }
        }
    }
}

@Composable
fun App() {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("tracelink", Context.MODE_PRIVATE) }
    var api by remember { mutableStateOf<Api?>(null) }
    var devices by remember { mutableStateOf<List<Device>>(emptyList()) }
    var shown by remember { mutableStateOf<Pair<Device, Challenge>?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    fun work(block: () -> Unit) {
        busy = true
        message = null
        thread {
            try {
                block()
            } catch (e: ApiException) {
                message = e.message
            } catch (e: Exception) {
                message = "Something went wrong. Try again."
            }
            busy = false
        }
    }

    val current = api
    val code = shown
    when {
        current == null -> LoginScreen(
            initialUrl = prefs.getString("url", "http://localhost:8000") ?: "",
            initialEmail = prefs.getString("email", "") ?: "",
            busy = busy,
            message = message,
        ) { url, email, password ->
            work {
                val client = Api(url)
                client.login(email, password)
                devices = client.devices()
                prefs.edit().putString("url", url).putString("email", email).apply()
                api = client
            }
        }

        code != null -> CodeScreen(code.first, code.second) { shown = null }

        else -> DevicesScreen(
            devices = devices,
            busy = busy,
            message = message,
            onRefresh = { work { devices = current.devices() } },
            onShowCode = { d -> work { shown = d to current.showCode(d.id) } },
            onSignOut = { api = null; devices = emptyList(); message = null },
        )
    }
}

@Composable
fun LoginScreen(
    initialUrl: String,
    initialEmail: String,
    busy: Boolean,
    message: String?,
    onSignIn: (String, String, String) -> Unit,
) {
    var url by remember { mutableStateOf(initialUrl) }
    var email by remember { mutableStateOf(initialEmail) }
    var password by remember { mutableStateOf("") }
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Spacer(Modifier.height(32.dp))
        Text("TraceLink", fontSize = 32.sp, fontWeight = FontWeight.ExtraBold)
        Text("Sign in with the same account you use on the website.")
        OutlinedTextField(
            value = url, onValueChange = { url = it }, label = { Text("Server address") },
            supportingText = { Text("With the USB route use http://localhost:8000. Without it, your laptop IP and port 8000") },
            singleLine = true, modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = email, onValueChange = { email = it }, label = { Text("Email") },
            singleLine = true, modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = password, onValueChange = { password = it }, label = { Text("Password") },
            visualTransformation = PasswordVisualTransformation(),
            singleLine = true, modifier = Modifier.fillMaxWidth(),
        )
        if (message != null) Text(message, color = MaterialTheme.colorScheme.error)
        Button(
            onClick = { onSignIn(url, email, password) },
            enabled = !busy && url.isNotBlank() && email.isNotBlank() && password.isNotBlank(),
            modifier = Modifier.fillMaxWidth(),
        ) { Text(if (busy) "Please wait..." else "Sign in") }
    }
}

@Composable
fun DevicesScreen(
    devices: List<Device>,
    busy: Boolean,
    message: String?,
    onRefresh: () -> Unit,
    onShowCode: (Device) -> Unit,
    onSignOut: () -> Unit,
) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Spacer(Modifier.height(24.dp))
        Text("Your phones", fontSize = 28.sp, fontWeight = FontWeight.ExtraBold)
        Text("Pick the phone you are holding. Add phones on the website first.")
        if (message != null) Text(message, color = MaterialTheme.colorScheme.error)
        if (devices.isEmpty()) Text("No phones yet. Add one on the website, then tap Refresh.")
        devices.forEach { d ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(d.nickname, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                    Text(d.model)
                    if (d.status == "verified") {
                        Text("Ownership confirmed", color = MaterialTheme.colorScheme.primary)
                    } else {
                        Button(onClick = { onShowCode(d) }, enabled = !busy) { Text("Show my code") }
                    }
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedButton(onClick = onRefresh, enabled = !busy) { Text("Refresh") }
            OutlinedButton(onClick = onSignOut) { Text("Sign out") }
        }
    }
}

@Composable
fun CodeScreen(device: Device, challenge: Challenge, onBack: () -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(device.nickname, fontSize = 20.sp)
        Spacer(Modifier.height(8.dp))
        Text("Your code", fontWeight = FontWeight.Bold)
        Text(
            challenge.code.chunked(3).joinToString(" "),
            fontSize = 56.sp, fontWeight = FontWeight.ExtraBold, letterSpacing = 4.sp,
        )
        Spacer(Modifier.height(12.dp))
        Text("On the TraceLink website, choose this phone, tap \"Prove this phone is yours\" and type these 6 digits. The code works for 10 minutes and only once.")
        Spacer(Modifier.height(24.dp))
        OutlinedButton(onClick = onBack) { Text("Back") }
    }
}
