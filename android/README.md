# TraceLink Android app (step 1: show the ownership code on the phone)

This step has no Bluetooth yet. It does one thing: the phone you hold shows the 6-digit code, and you type it on the website.

## Set up (once)

1. Android Studio > New Project > **Empty Activity** (Jetpack Compose).
   Name: `TraceLink`. **Package name: `com.tracelink.app`**. Minimum SDK: API 26. Finish and wait for Gradle to sync.
   (If your package name is different, change the first line `package ...` in both files below to match yours.)
2. Copy `Api.kt` and `MainActivity.kt` from the `files` folder into `app/src/main/java/com/tracelink/app/`. Replace the existing `MainActivity.kt`.
   You can delete the wizard's `ui/theme` folder or leave it; it is not used.
3. Open `app/src/main/AndroidManifest.xml`:
   - Inside `<manifest>`, above `<application>`, add: `<uses-permission android:name="android.permission.INTERNET" />`
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
