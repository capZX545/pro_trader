/* ProTrader Advanced TradingView Chart - lightweight-charts v4 */
(function(){
'use strict';

let chart = null;
let candleSeries = null;
let volumeSeries = null;
let overlays = {}; // key -> series
let signalMarkers = [];
let priceLines = {}; // for SL/TP and levels
let drawings = []; // trendlines, hlines
let crosshairMoveSub = null;
let lastData = null;

const COLORS = {
  bg: '#0b0e14',
  panel: '#131722',
  text: '#d1d4dc',
  muted: '#787b86',
  green: '#26a69a',
  red: '#ef5350',
  grid: '#1f2633',
  border: '#2a2e39',
  yellow: '#ffb74d',
};

function ensureLib(){
  if(window.LightweightCharts) return Promise.resolve();
  return new Promise((res, rej)=>{
    const s = document.createElement('script');
    s.src = 'https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js';
    s.onload = ()=>res();
    s.onerror = ()=>{
      // fallback to local if exists or second CDN
      const s2 = document.createElement('script');
      s2.src = 'https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js';
      s2.onload = ()=>res();
      s2.onerror = ()=>rej('Failed to load lightweight-charts');
      document.head.appendChild(s2);
    };
    document.head.appendChild(s);
  });
}

function init(containerId){
  return ensureLib().then(()=>{
    const container = document.getElementById(containerId);
    if(!container) throw 'container not found';
    
    // Clear container
    container.innerHTML = '';
    
    const { createChart, ColorType } = LightweightCharts;
    
    chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight || 500,
      layout: {
        background: { type: ColorType.Solid, color: COLORS.bg },
        textColor: COLORS.text,
        fontFamily: 'Inter, -apple-system, Segoe UI, Roboto, sans-serif',
        fontSize: 12,
      },
      grid: {
        vertLines: { color: COLORS.grid, style: 1, visible: true },
        horzLines: { color: COLORS.grid, style: 1, visible: true },
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: { width: 1, color: '#5c9bff88', style: 2, labelBackgroundColor: '#2962ff' },
        horzLine: { width: 1, color: '#5c9bff88', style: 2, labelBackgroundColor: '#2962ff' },
      },
      rightPriceScale: {
        borderColor: COLORS.border,
        scaleMargins: { top: 0.1, bottom: 0.15 },
        entireTextOnly: false,
        visible: true,
        ticksVisible: true,
      },
      timeScale: {
        borderColor: COLORS.border,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 6,
        barSpacing: 6,
        minBarSpacing: 2,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
    });
    
    // Candlestick series
    candleSeries = chart.addCandlestickSeries({
      upColor: COLORS.green,
      downColor: COLORS.red,
      borderVisible: false,
      wickUpColor: COLORS.green,
      wickDownColor: COLORS.red,
      priceFormat: { type: 'price', precision: 6, minMove: 0.000001 },
    });
    
    // Volume series in separate pane - use histogram
    volumeSeries = chart.addHistogramSeries({
      priceScaleId: 'volume',
      priceFormat: { type: 'volume' },
      priceLineVisible: false,
      lastValueVisible: false,
    });
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });
    
    // Resize observer
    const ro = new ResizeObserver(entries=>{
      if(!chart) return;
      const entry = entries[0];
      if(entry){
        chart.applyOptions({ 
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    ro.observe(container);
    
    // Crosshair move for OHLC display
    chart.subscribeCrosshairMove(param=>{
      if(!param || !param.time || !lastData) return;
      const data = param.seriesData.get(candleSeries);
      if(!data) return;
      
      const el = document.getElementById('tv-ohlc');
      if(!el) return;
      
      const o = data.open, h = data.high, l = data.low, c = data.close;
      const chg = ((c - o) / o * 100);
      const chgColor = chg >= 0 ? COLORS.green : COLORS.red;
      
      // Find volume for this time
      let vol = '';
      if(volumeSeries){
        const vd = param.seriesData.get(volumeSeries);
        if(vd && vd.value) vol = ` Vol ${Number(vd.value).toLocaleString()}`;
      }
      
      el.innerHTML = `<span style="color:${COLORS.muted}">O</span> <b>${fmtPrice(o)}</b> <span style="color:${COLORS.muted}">H</span> <b>${fmtPrice(h)}</b> <span style="color:${COLORS.muted}">L</span> <b>${fmtPrice(l)}</b> <span style="color:${COLORS.muted}">C</span> <b>${fmtPrice(c)}</b> <span style="color:${chgColor}">${chg>=0?'+':''}${chg.toFixed(2)}%</span><span style="color:${COLORS.muted}">${vol}</span>`;
    });
    
    return chart;
  });
}

function fmtPrice(p){
  if(p==null) return '—';
  const n = Number(p);
  if(n>=1000) return n.toLocaleString(undefined,{maximumFractionDigits:2});
  if(n>=1) return n.toLocaleString(undefined,{maximumFractionDigits:4});
  return n.toLocaleString(undefined,{maximumSignificantDigits:6});
}

function setData(candles, options={}){
  if(!candleSeries || !volumeSeries) return;
  
  lastData = candles;
  
  // candles: {t:[], o:[], h:[], l:[], c:[], v:[]}
  const data = [];
  const volData = [];
  
  for(let i=0;i<candles.t.length;i++){
    const time = candles.t[i];
    // lightweight-charts expects time as unix timestamp or BusinessDay
    // We use timestamp
    const t = typeof time === 'number' ? time : Math.floor(new Date(time*1000).getTime()/1000);
    data.push({
      time: t,
      open: candles.o[i],
      high: candles.h[i],
      low: candles.l[i],
      close: candles.c[i],
    });
    volData.push({
      time: t,
      value: candles.v[i],
      color: candles.c[i] >= candles.o[i] ? COLORS.green+'88' : COLORS.red+'88',
    });
  }
  
  candleSeries.setData(data);
  
  // Apply price format based on symbol
  const precision = options.precision || 6;
  candleSeries.applyOptions({
    priceFormat: { type: 'price', precision: precision, minMove: Math.pow(10, -precision) },
  });
  
  volumeSeries.setData(volData);
  
  // Fit content if no view specified
  if(!options.keepView){
    chart.timeScale().fitContent();
  }
}

function addOverlay(key, values, times, color, options={}){
  if(!chart) return;
  
  // Remove existing
  if(overlays[key]){
    try{ chart.removeSeries(overlays[key]); }catch(e){}
    delete overlays[key];
  }
  
  const series = chart.addLineSeries({
    color: color || '#5c9bff',
    lineWidth: options.lineWidth || 1.5,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
    lineStyle: options.dashed ? 2 : 0,
  });
  
  const data = [];
  for(let i=0;i<values.length;i++){
    if(values[i]==null) continue;
    const t = typeof times[i] === 'number' ? times[i] : Math.floor(times[i]);
    data.push({ time: t, value: values[i] });
  }
  
  series.setData(data);
  overlays[key] = series;
  return series;
}

function clearOverlays(){
  Object.keys(overlays).forEach(k=>{
    try{ chart.removeSeries(overlays[k]); }catch(e){}
  });
  overlays = {};
}

function setSignals(signals, candles){
  if(!candleSeries) return;
  
  // signals: array of {i, time, side, px, sl, tp}
  // Convert to markers
  const markers = [];
  
  signals.forEach(s=>{
    const time = typeof s.t === 'number' ? s.t : Math.floor(s.time);
    if(s.side===1){
      markers.push({
        time: time,
        position: 'belowBar',
        color: COLORS.green,
        shape: 'arrowUp',
        text: 'Long',
        size: 1.2,
      });
    } else if(s.side===-1){
      markers.push({
        time: time,
        position: 'aboveBar',
        color: COLORS.red,
        shape: 'arrowDown',
        text: 'Short',
        size: 1.2,
      });
    }
  });
  
  // Sort by time
  markers.sort((a,b)=>a.time-b.time);
  
  candleSeries.setMarkers(markers);
  signalMarkers = markers;
}

function addPriceLine(price, color, title, options={}){
  if(!candleSeries) return null;
  
  const line = {
    price: price,
    color: color || '#ff9800',
    lineWidth: options.lineWidth || 1,
    lineStyle: options.dashed ? 2 : 0,
    axisLabelVisible: true,
    title: title || '',
  };
  
  const pl = candleSeries.createPriceLine(line);
  const id = Date.now() + Math.random();
  priceLines[id] = pl;
  return id;
}

function clearPriceLines(){
  Object.values(priceLines).forEach(pl=>{
    try{ candleSeries.removePriceLine(pl); }catch(e){}
  });
  priceLines = {};
}

function addDrawing(type, points, color){
  // For now, drawings as price lines or trend lines via line series
  if(type==='hline'){
    return addPriceLine(points[0], color||'#facc15', 'H-Line', {dashed:false});
  }
  if(type==='trend' && points.length===2){
    // Create line series for trend
    const key = 'drawing_'+Date.now();
    const times = points.map(p=>p.time);
    const values = points.map(p=>p.price);
    return addOverlay(key, values, times, color||'#facc15', {lineWidth:2});
  }
  return null;
}

function screenshot(){
  if(!chart) return null;
  return chart.takeScreenshot();
}

function setChartType(type){
  // type: 'candle', 'line', 'area', 'heikin-ashi'
  // For simplicity, we keep candlestick but can switch to line
  if(!chart || !candleSeries) return;
  
  if(type==='line'){
    // Convert candle to line series
    try{ chart.removeSeries(candleSeries); }catch(e){}
    candleSeries = chart.addLineSeries({
      color: '#2962ff',
      lineWidth: 2,
    });
    if(lastData){
      const data = [];
      for(let i=0;i<lastData.t.length;i++){
        const t = typeof lastData.t[i]==='number'?lastData.t[i]:Math.floor(lastData.t[i]);
        data.push({ time: t, value: lastData.c[i] });
      }
      candleSeries.setData(data);
    }
  } else if(type==='candle'){
    try{ chart.removeSeries(candleSeries); }catch(e){}
    candleSeries = chart.addCandlestickSeries({
      upColor: COLORS.green,
      downColor: COLORS.red,
      borderVisible: false,
      wickUpColor: COLORS.green,
      wickDownColor: COLORS.red,
    });
    if(lastData) setData(lastData, {keepView:true});
  } else if(type==='area'){
    try{ chart.removeSeries(candleSeries); }catch(e){}
    candleSeries = chart.addAreaSeries({
      topColor: '#2962ff88',
      bottomColor: '#2962ff00',
      lineColor: '#2962ff',
      lineWidth: 2,
    });
    if(lastData){
      const data = [];
      for(let i=0;i<lastData.t.length;i++){
        const t = typeof lastData.t[i]==='number'?lastData.t[i]:Math.floor(lastData.t[i]);
        data.push({ time: t, value: lastData.c[i] });
      }
      candleSeries.setData(data);
    }
  }
}

function applyTheme(isDark){
  if(!chart) return;
  chart.applyOptions({
    layout: {
      background: { type: LightweightCharts.ColorType.Solid, color: isDark ? COLORS.bg : '#ffffff' },
      textColor: isDark ? COLORS.text : '#131722',
    },
    grid: {
      vertLines: { color: isDark ? COLORS.grid : '#e0e3eb' },
      horzLines: { color: isDark ? COLORS.grid : '#e0e3eb' },
    },
  });
}

// Expose
window.TVAdvanced = {
  init,
  setData,
  addOverlay,
  clearOverlays,
  setSignals,
  addPriceLine,
  clearPriceLines,
  addDrawing,
  screenshot,
  setChartType,
  applyTheme,
  get chart(){ return chart; },
  get candleSeries(){ return candleSeries; },
};

})();
