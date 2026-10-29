package com.tracelink.app

import org.junit.Assert.assertEquals
import org.junit.Test

/** Same test vector as backend/tests/test_beacon.py. If this fails, phone and server disagree. */
class BeaconTest {
    private val secret = ByteArray(32) { it.toByte() }

    @Test fun windowOneThousand() = assertEquals("49fddab5e57da4b6", Beacon.hex(Beacon.id(secret, 1000)))

    @Test fun windowOneThousandAndOne() = assertEquals("89ea7a65868fb23c", Beacon.hex(Beacon.id(secret, 1001)))

    @Test fun windowMath() {
        assertEquals(1000L, Beacon.window(1000L * 900 * 1000))
        assertEquals(1000L, Beacon.window((1000L * 900 + 899) * 1000))
        assertEquals(1001L, Beacon.window(1001L * 900 * 1000))
    }
}
