package com.tracelink.app

import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * Rotating Bluetooth ID. Must match backend/app/beacon.py exactly:
 *   id = first 8 bytes of HMAC-SHA256(secret, "tracelink-beacon:" + window)
 *   window = unix seconds / 900
 * Pure Kotlin (no Android classes) so it runs in an ordinary unit test.
 */
object Beacon {
    const val WINDOW_SECONDS = 900L
    const val ID_BYTES = 8
    private const val PREFIX = "tracelink-beacon:"

    fun window(epochMillis: Long): Long = (epochMillis / 1000) / WINDOW_SECONDS

    fun id(secret: ByteArray, window: Long): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(secret, "HmacSHA256"))
        return mac.doFinal((PREFIX + window.toString()).toByteArray(Charsets.US_ASCII)).copyOf(ID_BYTES)
    }

    fun hex(bytes: ByteArray): String = bytes.joinToString("") { "%02x".format(it) }
}
