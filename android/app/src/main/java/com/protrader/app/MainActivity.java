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

/** ProTrader mobile: the complete desktop engine (Python) served locally + the responsive web UI in a WebView. */
public class MainActivity extends AppCompatActivity {
    private WebView web;
    private LinearLayout splash;
    private ValueCallback<Uri[]> filePathCallback;   // Vision page: upload a chart screenshot
    private static final int FILE_REQ = 41;
    private int port = 0;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // Phase 23: Android 13+ requires a runtime grant before signal notifications can be shown
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
        s.setSupportZoom(false);
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
        TextView brand = new TextView(this);
        brand.setText("◆ ProTrader");
        brand.setTextColor(Color.WHITE);
        brand.setTextSize(28);
        brand.setGravity(Gravity.CENTER);
        ProgressBar pb = new ProgressBar(this);
        TextView msg = new TextView(this);
        msg.setText(R.string.starting);
        msg.setTextColor(Color.parseColor("#787b86"));
        msg.setGravity(Gravity.CENTER);
        msg.setPadding(40, 20, 40, 0);
        splash.addView(brand); splash.addView(pb); splash.addView(msg);
        root.addView(splash);
        setContentView(root);

        // keep the engine alive (forward test / alerts) while the app is backgrounded
        Intent svc = new Intent(this, EngineService.class);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(svc); else startService(svc);

        new Thread(() -> {
            if (!Python.isStarted()) Python.start(new AndroidPlatform(this));
            PyObject m = Python.getInstance().getModule("ptmobile");
            port = m.callAttr("start", 8765).toInt();
            new Handler(Looper.getMainLooper()).post(() -> {
                web.loadUrl("http://127.0.0.1:" + port + "/");
                web.setVisibility(View.VISIBLE);
                splash.setVisibility(View.GONE);
            });
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
