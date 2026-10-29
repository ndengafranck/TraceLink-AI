package com.tracelink.app

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class ApiException(message: String) : Exception(message)

data class Device(val id: String, val nickname: String, val model: String, val status: String)
data class Challenge(val code: String, val expiresAt: String)

/** Talks to the TraceLink backend. Plain Java networking, no extra libraries. */
class Api(baseUrl: String) {
    private val base = baseUrl.trim().trimEnd('/')
    private var token: String? = null

    private fun call(method: String, path: String, body: JSONObject? = null): String {
        val conn = URL(base + path).openConnection() as HttpURLConnection
        try {
            conn.requestMethod = method
            conn.connectTimeout = 8000
            conn.readTimeout = 15000
            conn.setRequestProperty("Accept", "application/json")
            token?.let { conn.setRequestProperty("Authorization", "Bearer $it") }
            if (method == "POST") {
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json")
                conn.outputStream.use { it.write((body ?: JSONObject()).toString().toByteArray()) }
            }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
            if (code !in 200..299) throw ApiException(errorText(code, text))
            return text
        } catch (e: ApiException) {
            throw e
        } catch (e: Exception) {
            throw ApiException(
                "Cannot reach the server at $base. Same Wi-Fi? Backend started with --host 0.0.0.0?"
            )
        } finally {
            conn.disconnect()
        }
    }

    private fun errorText(code: Int, text: String): String {
        try {
            val detail = JSONObject(text).opt("detail")
            if (detail is String) return detail
            if (detail is JSONArray && detail.length() > 0) {
                return detail.getJSONObject(0).optString("msg", "Invalid input")
            }
        } catch (_: Exception) {
        }
        return if (code >= 500) "The server had a problem. Try again." else "Request failed ($code)"
    }

    fun login(email: String, password: String) {
        val body = JSONObject().put("email", email.trim()).put("password", password)
        token = JSONObject(call("POST", "/auth/login", body)).getString("access_token")
    }

    fun devices(): List<Device> {
        val arr = JSONArray(call("GET", "/devices"))
        return (0 until arr.length()).map {
            val o = arr.getJSONObject(it)
            Device(o.getString("id"), o.getString("nickname"), o.getString("model"), o.getString("status"))
        }
    }

    /** Ask the server for an ownership code. It is shown on THIS phone's screen. */
    fun showCode(deviceId: String): Challenge {
        val o = JSONObject(call("POST", "/companion/devices/$deviceId/challenge"))
        return Challenge(o.getString("code"), o.getString("expires_at"))
    }

    /** The verified phone gets its beacon secret (the same one again if asked twice). */
    fun enroll(deviceId: String): ByteArray {
        val o = JSONObject(call("POST", "/companion/devices/$deviceId/enroll"))
        return java.util.Base64.getUrlDecoder().decode(o.getString("beacon_secret"))
    }

    /** A finder phone says: I heard this beacon here. The server always answers "received". */
    fun report(beaconId: String, observedAt: String, lat: Double, lon: Double, accuracyM: Double, nonce: String) {
        val body = JSONObject()
            .put("beacon_id", beaconId)
            .put("observed_at", observedAt)
            .put("lat", lat)
            .put("lon", lon)
            .put("accuracy_m", accuracyM)
            .put("nonce", nonce)
        call("POST", "/reports", body)
    }
}
