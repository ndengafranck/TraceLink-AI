package com.tracelink.app

import android.annotation.SuppressLint
import android.bluetooth.BluetoothManager
import android.bluetooth.le.AdvertiseCallback
import android.bluetooth.le.AdvertiseData
import android.bluetooth.le.AdvertiseSettings
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import android.os.SystemClock

/**
 * One 16-bit service UUID carries the 8-byte rotating ID as service data.
 * Advertisement size: 4 bytes (UUID list) + 12 bytes (service data) = 16 of the 31 allowed.
 * Both test phones advertise legacy 31-byte packets, so nothing more is needed.
 */
val SERVICE_UUID: ParcelUuid = ParcelUuid.fromString("0000fff4-0000-1000-8000-00805f9b34fb")

fun bluetoothPermissions(finder: Boolean): Array<String> {
    val list = mutableListOf<String>()
    if (Build.VERSION.SDK_INT >= 31) {
        list += if (finder) android.Manifest.permission.BLUETOOTH_SCAN else android.Manifest.permission.BLUETOOTH_ADVERTISE
    }
    // Finder needs the GPS position; on Android 11 and older scanning also needs location.
    if (finder) list += android.Manifest.permission.ACCESS_FINE_LOCATION
    return list.toTypedArray()
}

/** Broadcasts this phone's rotating ID. Changes the ID when the 15-minute window changes. */
@SuppressLint("MissingPermission")
class Broadcaster(private val context: Context, private val onStatus: (String) -> Unit) {
    private val handler = Handler(Looper.getMainLooper())
    private var secret: ByteArray? = null
    private var window = -1L
    private var running = false

    var currentId: String = ""
        private set

    private val callback = object : AdvertiseCallback() {
        override fun onStartSuccess(settingsInEffect: AdvertiseSettings) = onStatus("Broadcasting")
        override fun onStartFailure(errorCode: Int) = onStatus(
            when (errorCode) {
                ADVERTISE_FAILED_FEATURE_UNSUPPORTED -> "This phone cannot advertise over Bluetooth LE"
                ADVERTISE_FAILED_TOO_MANY_ADVERTISERS -> "Another app is using all Bluetooth advertising slots"
                ADVERTISE_FAILED_DATA_TOO_LARGE -> "Advertisement too large"
                else -> "Bluetooth advertising failed (code $errorCode)"
            }
        )
    }

    private val tick = object : Runnable {
        override fun run() {
            if (!running) return
            val w = Beacon.window(System.currentTimeMillis())
            if (w != window) advertise(w)
            handler.postDelayed(this, 15_000)
        }
    }

    private fun adapter() = (context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter

    private fun advertise(newWindow: Long) {
        val s = secret ?: return
        val advertiser = adapter()?.bluetoothLeAdvertiser
        if (advertiser == null) {
            onStatus("Bluetooth is off or not available")
            return
        }
        advertiser.stopAdvertising(callback)
        val id = Beacon.id(s, newWindow)
        val settings = AdvertiseSettings.Builder()
            .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_BALANCED)
            .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_MEDIUM)
            .setConnectable(false)
            .setTimeout(0)
            .build()
        val data = AdvertiseData.Builder()
            .setIncludeDeviceName(false)
            .setIncludeTxPowerLevel(false)
            .addServiceUuid(SERVICE_UUID)
            .addServiceData(SERVICE_UUID, id)
            .build()
        window = newWindow
        currentId = Beacon.hex(id)
        advertiser.startAdvertising(settings, data, callback)
    }

    fun start(secret: ByteArray) {
        this.secret = secret
        running = true
        window = -1L
        handler.post(tick)
    }

    fun stop() {
        running = false
        handler.removeCallbacks(tick)
        try {
            adapter()?.bluetoothLeAdvertiser?.stopAdvertising(callback)
        } catch (_: Exception) {
        }
        secret = null
        currentId = ""
        onStatus("Stopped")
    }
}

/** Listens for TraceLink beacons and reports each ID it hears (the server decides what matches). */
@SuppressLint("MissingPermission")
class Finder(private val context: Context, private val onHeard: (id: String, rssi: Int) -> Unit, private val onStatus: (String) -> Unit) {
    private var scanning = false

    private val callback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            val data = result.scanRecord?.getServiceData(SERVICE_UUID) ?: return
            if (data.size != Beacon.ID_BYTES) return
            onHeard(Beacon.hex(data), result.rssi)
        }

        override fun onScanFailed(errorCode: Int) = onStatus("Scan failed (code $errorCode)")
    }

    fun start() {
        val scanner = (context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager)
            .adapter?.bluetoothLeScanner
        if (scanner == null) {
            onStatus("Bluetooth is off or not available")
            return
        }
        val filters = listOf(ScanFilter.Builder().setServiceUuid(SERVICE_UUID).build())
        val settings = ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build()
        scanner.startScan(filters, settings, callback)
        scanning = true
        onStatus("Scanning")
    }

    fun stop() {
        if (!scanning) return
        try {
            (context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager)
                .adapter?.bluetoothLeScanner?.stopScan(callback)
        } catch (_: Exception) {
        }
        scanning = false
        onStatus("Stopped")
    }
}

/** Keeps the newest GPS/network fix so a heard beacon can be tagged with where it was heard. */
@SuppressLint("MissingPermission")
class LocationTracker(context: Context) {
    private val manager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
    private var latest: Location? = null

    private val listener = object : LocationListener {
        override fun onLocationChanged(location: Location) {
            latest = location
        }

        @Deprecated("Deprecated in Java")
        override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
        override fun onProviderEnabled(provider: String) {}
        override fun onProviderDisabled(provider: String) {}
    }

    fun start() {
        for (p in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) {
            if (manager.isProviderEnabled(p)) {
                manager.requestLocationUpdates(p, 2000L, 0f, listener, Looper.getMainLooper())
                manager.getLastKnownLocation(p)?.let { if (isBetter(it)) latest = it }
            }
        }
    }

    fun stop() = manager.removeUpdates(listener)

    fun enabled(): Boolean =
        manager.isProviderEnabled(LocationManager.GPS_PROVIDER) || manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)

    private fun isBetter(l: Location) = latest == null || l.elapsedRealtimeNanos > latest!!.elapsedRealtimeNanos

    /** Newest fix no older than maxAgeMs, otherwise null (never report a stale position). */
    fun fresh(maxAgeMs: Long = 60_000): Location? {
        val l = latest ?: return null
        val ageMs = (SystemClock.elapsedRealtimeNanos() - l.elapsedRealtimeNanos) / 1_000_000
        return if (ageMs in 0..maxAgeMs) l else null
    }
}
