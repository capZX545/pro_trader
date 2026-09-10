package com.protrader.app;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.graphics.Color;
import android.view.Gravity;
import android.widget.LinearLayout;

import androidx.appcompat.app.AppCompatActivity;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

/** ProTrader mobile: Complete desktop engine (196 strategies, TradingView chart) - Fast, offline, no extra installs */
public class MainActivity extends AppCompatActivity {
    private WebView web;
    private LinearLayout splash;
    private ValueCallback<Uri[]> filePathCallback;
    private static final int FILE_REQ = 41;
    private int port = 0;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (android.os.Build.VERSION.SDK_INT >= 33
                && checkSelfPermission("android.permission.POST_NOTIFICATIONS") != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 7231);
        }
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor("#0b0e14"));
        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#0b0e14"));
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setAllowFileAccessFromFileURLs(true);
        s.setAllowUniversalAccessFromFileURLs(true);
        s.setSupportZoom(true);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, String url) {
                if (url.startsWith("http://127.0.0.1")) return false;
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (filePathCallback != null) filePathCallback.onReceiveValue(null);
                filePathCallback = cb;
                Intent i = p.createIntent();
                i.setType("image/*");
                try { startActivityForResult(i, FILE_REQ); } catch (Exception e) { filePathCallback = null; return false; }
                return true;
            }
        });
        web.setVisibility(View.INVISIBLE);
        root.addView(web);

        splash = new LinearLayout(this);
        splash.setOrientation(LinearLayout.VERTICAL);
        splash.setGravity(Gravity.CENTER);
        splash.setBackgroundColor(Color.parseColor("#0b0e14"));
        
        TextView brand = new TextView(this);
        brand.setText("◆ ProTrader");
        brand.setTextColor(Color.WHITE);
        brand.setTextSize(32);
        brand.setGravity(Gravity.CENTER);
        brand.setTypeface(null, android.graphics.Typeface.BOLD);
        
        TextView sub = new TextView(this);
        sub.setText("Advanced TradingView Chart \u2022 196 Strategies \u2022 All Markets");
        sub.setTextColor(Color.parseColor("#5c9bff"));
        sub.setTextSize(12);
        sub.setGravity(Gravity.CENTER);
        sub.setPadding(20, 8, 20, 0);
        
        ProgressBar pb = new ProgressBar(this);
        pb.getIndeterminateDrawable().setColorFilter(Color.parseColor("#2962ff"), android.graphics.PorterDuff.Mode.SRC_IN);
        
        TextView msg = new TextView(this);
        msg.setText(R.string.starting);
        msg.setTextColor(Color.parseColor("#787b86"));
        msg.setGravity(Gravity.CENTER);
        msg.setPadding(40, 20, 40, 0);
        msg.setTextSize(11);
        
        TextView features = new TextView(this);
        features.setText("\u2713 196 Strategies  \u2713 TradingView Chart  \u2713 Iran Gold  \u2713 All Markets  \u2713 Offline Ready");
        features.setTextColor(Color.parseColor("#26a69a"));
        features.setGravity(Gravity.CENTER);
        features.setPadding(20, 30, 20, 0);
        features.setTextSize(10);
        
        splash.addView(brand); 
        splash.addView(sub);
        splash.addView(pb); 
        splash.addView(msg);
        splash.addView(features);
        root.addView(splash);
        setContentView(root);

        Intent svc = new Intent(this, EngineService.class);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(svc); else startService(svc);

        new Thread(() -> {
            try {
                long startTime = System.currentTimeMillis();
                if (!Python.isStarted()) {
                    Python.start(new AndroidPlatform(this));
                }
                PyObject m = Python.getInstance().getModule("ptmobile");
                for (int i=0; i<3; i++) {
                    try {
                        port = m.callAttr("start", 8765).toInt();
                        break;
                    } catch (Exception e) {
                        if (i==2) throw e;
                        Thread.sleep(500);
                    }
                }
                long elapsed = System.currentTimeMillis() - startTime;
                long remaining = Math.max(0, 1000 - elapsed);
                if (remaining > 0) Thread.sleep(remaining);
                
                new Handler(Looper.getMainLooper()).post(() -> {
                    web.loadUrl("http://127.0.0.1:" + port + "/");
                    web.setVisibility(View.VISIBLE);
                    splash.setVisibility(View.GONE);
                });
            } catch (Exception e) {
                new Handler(Looper.getMainLooper()).post(() -> {
                    msg.setText("Error: " + e.getMessage() + "\nTap to retry");
                    splash.setOnClickListener(v -> recreate());
                });
            }
        }, "protrader-engine").start();
    }

    @Override protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req == FILE_REQ && filePathCallback != null) {
            filePathCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(res, data));
            filePathCallback = null;
        }
    }

    @Override public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack(); else super.onBackPressed();
    }
}
