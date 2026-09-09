package com.protrader.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import androidx.core.app.NotificationCompat;

/** Foreground service so Android does not kill the Python engine (live signals, forward test, Telegram/desktop alerts). */
public class EngineService extends Service {
    private static final String CH = "protrader_engine";

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CH, getString(R.string.channel), NotificationManager.IMPORTANCE_LOW);
            nm.createNotificationChannel(ch);
        }
        PendingIntent pi = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class),
                Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0);
        Notification n = new NotificationCompat.Builder(this, CH)
                .setContentTitle(getString(R.string.app_name))
                .setContentText(getString(R.string.engine_running))
                .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
                .setContentIntent(pi).setOngoing(true).build();
        if (Build.VERSION.SDK_INT >= 29) startForeground(1, n, android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        else startForeground(1, n);
        return START_STICKY;
    }

    // ---- Phase 23: poll the local engine for new alerts and raise system notifications (works with the app in background)
    private final android.os.Handler h = new android.os.Handler(android.os.Looper.getMainLooper());
    private double since = System.currentTimeMillis() / 1000.0;
    private final Runnable poll = new Runnable() {
        @Override public void run() {
            new Thread(() -> {
                try {
                    java.net.HttpURLConnection c = (java.net.HttpURLConnection) new java.net.URL("http://127.0.0.1:8765/api/notifications?since=" + since).openConnection();
                    c.setConnectTimeout(3000); c.setReadTimeout(8000);
                    java.io.InputStream in = c.getInputStream();
                    java.util.Scanner sc = new java.util.Scanner(in, "UTF-8").useDelimiter("\\A");
                    String body = sc.hasNext() ? sc.next() : "";
                    org.json.JSONObject o = new org.json.JSONObject(body);
                    since = o.optDouble("now", since);
                    org.json.JSONArray items = o.optJSONArray("items");
                    if (items != null) {
                        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
                        if (Build.VERSION.SDK_INT >= 26) nm.createNotificationChannel(new NotificationChannel(CH + "_signals", "ProTrader signals", NotificationManager.IMPORTANCE_HIGH));
                        for (int i = 0; i < items.length(); i++) {
                            org.json.JSONObject it = items.getJSONObject(i);
                            org.json.JSONObject meta = it.optJSONObject("meta");
                            if (meta != null && "news_skip".equals(meta.optString("kind"))) continue;
                            PendingIntent pi = PendingIntent.getActivity(EngineService.this, 0, new Intent(EngineService.this, MainActivity.class), Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0);
                            Notification n = new NotificationCompat.Builder(EngineService.this, CH + "_signals")
                                    .setContentTitle(it.optString("title")).setContentText(it.optString("body"))
                                    .setStyle(new NotificationCompat.BigTextStyle().bigText(it.optString("body")))
                                    .setSmallIcon(android.R.drawable.stat_notify_more).setContentIntent(pi).setAutoCancel(true)
                                    .setPriority(NotificationCompat.PRIORITY_HIGH).build();
                            nm.notify(1000 + (int) (it.optDouble("ts", i) % 100000), n);
                        }
                    }
                } catch (Exception ignored) { }
            }).start();
            h.postDelayed(this, 60_000);
        }
    };

    @Override public void onCreate() { super.onCreate(); h.postDelayed(poll, 90_000); }
    @Override public void onDestroy() { h.removeCallbacks(poll); super.onDestroy(); }

    @Override public IBinder onBind(Intent intent) { return null; }
}
