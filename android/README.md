# TraceLink Android app

**Step 1:** the phone you hold shows the 6-digit ownership code.
**Step 2 (this version):** the phone can also broadcast its rotating Bluetooth ID, or act as a finder that listens for other TraceLink phones and reports where it heard them.

Files in `files/`: `Api.kt`, `Beacon.kt`, `Ble.kt`, `BleScreens.kt`, `MainActivity.kt`. Test in `test/BeaconTest.kt`.

> Not compiled by me: my sandbox has no Android SDK. `Beacon.kt` is compiled and checked against the server's test vector (`49fddab5e57da4b6`). The rest has been read line by line but never run. If Android Studio shows a red error, send me a screenshot of it.

## Set up (once)

1. Android Studio > New Project > **Empty Activity** (Jetpack Compose).
   Name: `TraceLink`. **Package name: `com.tracelink.app`**. Minimum SDK: API 26. Finish and wait for Gradle to sync.
   (If your package name is different, change the first line `package ...` in both files below to match yours.)
2. Copy ALL FIVE files from the `files` folder (`Api.kt`, `Beacon.kt`, `Ble.kt`, `BleScreens.kt`, `MainActivity.kt`) into `app/src/main/java/com/tracelink/app/`. Replace the existing `MainActivity.kt`.
   Copy `test/BeaconTest.kt` into `app/src/test/java/com/tracelink/app/` (optional: right-click it > Run to check the Bluetooth ID formula).
   You can delete the wizard's `ui/theme` folder or leave it; it is not used.
3. Open `app/src/main/AndroidManifest.xml`:
   - Inside `<manifest>`, above `<application>`, add all of these:
     ```xml
     <uses-permission android:name="android.permission.INTERNET" />
     <uses-permission android:name="android.permission.BLUETOOTH" android:maxSdkVersion="30" />
     <uses-permission android:name="android.permission.BLUETOOTH_ADMIN" android:maxSdkVersion="30" />
     <uses-permission android:name="android.permission.BLUETOOTH_SCAN" />
     <uses-permission android:name="android.permission.BLUETOOTH_ADVERTISE" />
     <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
     <uses-feature android:name="android.hardware.bluetooth_le" android:required="false" />
     ```
   - In the `<application ...>` tag, add: `android:usesCleartextTraffic="true"`
   (Cleartext is for local testing over plain HTTP only. A real deployment uses HTTPS.)
4. On the phone: Settings > About phone > tap **Build number** 7 times > Settings > Developer options > turn on **USB debugging**. Plug the phone into the laptop and tap **Allow** on the phone.
5. Click the green **Run** button in Android Studio and choose your phone.

## Easiest way to connect: USB (works even when your phone is the hotspot)

Wi-Fi often fails when the phone shares its internet with the laptop (Windows blocks the connection). Use the USB cable instead. With the phone plugged in and USB debugging on:

1. Open a terminal (PowerShell) and run:
   ```
   & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" devices
   ```
   Your phone must appear as `device` (accept the prompt on the phone if it says `unauthorized`).
2. Link the phone's `localhost` to your laptop:
   ```
   & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" reverse tcp:8000 tcp:8000
   & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" reverse tcp:5173 tcp:5173
   ```
   Run these again whenever you unplug and replug the phone.
3. Start the backend normally (`uvicorn app.main:app --reload`) and the website (`npm run dev`).
4. On the **phone**: open `http://localhost:8000/health` in its browser. It should show `{"status":"ok"}`. The website is at `http://localhost:5173`.
5. In the app, the server address is `http://localhost:8000`.

## Every time you test (Wi-Fi route, if you prefer it)

1. Backend: `uvicorn app.main:app --reload --host 0.0.0.0` (note `--host 0.0.0.0`: it lets the phone reach the laptop).
2. Phone and laptop on the same Wi-Fi (or the laptop on the phone's hotspot).
3. Check from the **phone's browser**: `http://<laptop IP>:8000/health` must show `{"status":"ok"}`. If not, fix the network/firewall first (Windows Firewall: allow Python on private networks).
4. Website (`npm run dev -- --host`): create an account, add the phone.
5. App: server address `http://<laptop IP>:8000`, sign in, tap **Show my code**.
6. Website: on that phone, click **Prove this phone is yours**, type the code, **Confirm code**. It should say "Checked on the phone".


## Bluetooth test with your two phones (step 2)

Roles: **Phone A** = the "lost" phone (broadcasts). **Phone B** = the finder (scans). Install the app on both (Run once per phone, choosing it in the device list).

If both phones are plugged into the laptop, run `adb reverse` for each one: `adb devices` shows two serial numbers, then
`adb -s <serial> reverse tcp:8000 tcp:8000` for each serial.

1. Website: add Phone A, then verify it with the code shown in the app (step 1 above). Sign in to the app on Phone A.
2. Phone A: tap **Broadcast my beacon** > **Start broadcasting** > allow Bluetooth. The screen shows "Broadcasting" and a 16-character ID. Leave the screen open.
3. Website: open Phone A's page > **Report as lost**.
4. Phone B: sign in (same account is fine) > **Open finder mode** > **Start scanning** > allow Bluetooth and location. Turn on Location in settings. Go near a window or outside so GPS gets a fix.
5. Within a minute Phone B shows "Reported a beacon" and the website case gets a **Bluetooth report** sighting on the map and list. Then try **Explain the evidence**.

If nothing is heard: use nRF Connect on Phone B > Scanner and look for a device with **Service Data** under UUID `0xFFF4` (8 bytes). If nRF sees it, the problem is in the finder; if it does not, the problem is broadcasting on Phone A.

Honest limits: foreground only (Android may stop Bluetooth in the background; a release would use a foreground service). The beacon secret is stored in the app's private storage, not hardware-backed storage. A finder could send a fake position; the server's rules and the "evidence, not proof" wording are the defence.
