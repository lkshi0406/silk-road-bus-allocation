import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Bell,
  Bus,
  CircleDot,
  Clock3,
  Pause,
  Play,
  Send,
  ShieldCheck,
  X,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  Circle,
  CircleMarker,
  MapContainer,
  Marker,
  Popup,
  Polyline,
  TileLayer,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const COLORS = {
  bg: '#0F1B2D',
  panel: '#1A2B42',
  card: '#1E3352',
  accent: '#2E7CF6',
  success: '#22C55E',
  warning: '#F59E0B',
  critical: '#EF4444',
  textPrimary: '#F0F4FF',
  textSecondary: '#94A3B8',
  border: '#2A3F5F',
};

const stops = [
  { name: 'Silk Board Junction', coords: [12.9176, 77.6229], load: 487, eta: '12 min', lastCount: 462 },
  { name: 'BTM Layout', coords: [12.9121, 77.6152], load: 210, eta: '7 min', lastCount: 205 },
  { name: 'HSR 8th Cross', coords: [12.9089, 77.6341], load: 89, eta: '6 min', lastCount: 80 },
  { name: 'Bommanahalli', coords: [12.9012, 77.6289], load: 340, eta: '10 min', lastCount: 329 },
  { name: 'Electronic City Phase 1', coords: [12.8458, 77.6692], load: 156, eta: '15 min', lastCount: 149 },
  { name: 'Kudlu Gate', coords: [12.8698, 77.6589], load: 78, eta: '9 min', lastCount: 71 },
  { name: 'Harlur Road', coords: [12.8901, 77.6712], load: 195, eta: '8 min', lastCount: 191 },
  { name: 'Agara Lake', coords: [12.9034, 77.6478], load: 67, eta: '6 min', lastCount: 61 },
];

const routePoints = stops.map((s) => s.coords);

const initialFleet = [
  { id: 'KA-01-F-2234', status: 'AVAILABLE', shift: 78, load: [34, 65], distance: 4.2 },
  { id: 'KA-02-B-8821', status: 'EN ROUTE', shift: 63, load: [48, 70], distance: 1.8 },
  { id: 'KA-03-C-1145', status: 'AVAILABLE', shift: 55, load: [28, 65], distance: 5.1 },
  { id: 'KA-04-D-7734', status: 'OFF SHIFT', shift: 12, load: [0, 60], distance: 9.6 },
  { id: 'KA-05-E-3392', status: 'DISPATCHED', shift: 41, load: [52, 65], distance: 2.4 },
  { id: 'KA-06-F-9901', status: 'AVAILABLE', shift: 89, load: [19, 60], distance: 6.3 },
];

const sourceRows = [
  ['BMTC GTFS', 'Live', COLORS.success],
  ['Weather API', 'Live', COLORS.success],
  ['Uber Movement', 'Cached', COLORS.warning],
  ['Metro Signal', 'Delayed 4m', COLORS.warning],
];

const chartData = [
  ['07:00', 102, 98],
  ['07:15', 121, 116],
  ['07:30', 155, 149],
  ['07:45', 241, 233],
  ['08:00', 312, 305],
  ['08:15', 487, null],
  ['08:30', 468, null],
  ['08:45', 399, null],
  ['09:00', 351, null],
  ['09:15', 290, null],
  ['09:30', 248, null],
  ['09:45', 208, null],
  ['10:00', 174, null],
].map(([time, predicted, actual]) => ({ time, predicted, actual }));

const defaultOverrides = [
  {
    id: 'o-1',
    tone: 'red',
    title: '08:07 AM  —  Override: Insufficient demand',
    stats: 'Predicted: 412 pax  |  Actual: 398 pax',
    badge: 'SYSTEM WAS CORRECT — Wait: 24 min',
    note: 'Dispatch would have saved ~13 min avg wait',
  },
  {
    id: 'o-2',
    tone: 'green',
    title: 'Yesterday 17:45  —  Override: Bus needed elsewhere',
    stats: 'Predicted: 380 pax  |  Actual: 201 pax',
    badge: 'OVERRIDE CORRECT — Low actual demand',
    note: '',
  },
  {
    id: 'o-3',
    tone: 'neutral',
    title: '08:09 AM  —  Override logged, awaiting outcome',
    stats: '',
    badge: 'PENDING — Result in 14:00',
    note: '',
    pendingSeconds: 14 * 60,
  },
];

const baselineFeed = [
  { id: 1, icon: '🔴', text: '08:07 Surge alert fired — Silk Board (487 pax)' },
  { id: 2, icon: '🟢', text: '08:05 Bus KA-02-B-8821 departed BTM Layout' },
  { id: 3, icon: '🟡', text: '08:03 Override logged — KA-01-F-2234' },
  { id: 4, icon: '🔵', text: '08:01 Model retrained — MAE improved 11.2 → 9.4' },
  { id: 5, icon: '🟢', text: '07:58 Dispatch approved — KA-05-E-3392' },
  { id: 6, icon: '🔴', text: '07:45 Surge alert fired — Bommanahalli (341 pax)' },
  { id: 7, icon: '🟡', text: '07:44 Weather update — Heavy rain detected' },
  { id: 8, icon: '🔵', text: '07:30 Scheduled retraining complete' },
];

const modeStyles = {
  live: 'text-success border-success shadow-[0_0_16px_rgba(34,197,94,0.35)]',
  replay: 'text-warning border-warning shadow-[0_0_16px_rgba(245,158,11,0.35)]',
  sim: 'text-accent border-accent shadow-[0_0_16px_rgba(46,124,246,0.35)]',
};

const cityOptions = [
  { value: 'bengaluru', label: '📍 Bengaluru — Silk Board', ready: true },
  { value: 'chennai', label: '📍 Chennai — Koyambedu', ready: false },
  { value: 'pune', label: '📍 Pune — Swargate', ready: false },
  { value: 'hyderabad', label: '📍 Hyderabad — MGBS', ready: false },
];

function two(n) {
  return String(n).padStart(2, '0');
}

function formatTimeFromMinutes(mins) {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${two(h)}:${two(m)}`;
}

function interpolateRoute(progress) {
  const points = routePoints;
  const segments = points.length - 1;
  const scaled = progress * segments;
  const idx = Math.min(Math.floor(scaled), segments - 1);
  const local = scaled - idx;
  const [aLat, aLng] = points[idx];
  const [bLat, bLng] = points[idx + 1];
  return [aLat + (bLat - aLat) * local, aLng + (bLng - aLng) * local];
}

function loadColor(load) {
  if (load > 300) return COLORS.critical;
  if (load >= 100) return COLORS.warning;
  return COLORS.success;
}

function loadRadius(load) {
  if (load > 300) return 13;
  if (load >= 100) return 10;
  return 8;
}

function statusPill(status) {
  switch (status) {
    case 'AVAILABLE':
      return 'bg-success/20 text-success border-success/50';
    case 'EN ROUTE':
      return 'bg-accent/20 text-accent border-accent/50';
    case 'DISPATCHED':
      return 'bg-warning/20 text-warning border-warning/50';
    default:
      return 'bg-slate-500/20 text-slate-300 border-slate-500/40';
  }
}

function AnimatedMarker({ position, emoji = '🚌' }) {
  const icon = useMemo(
    () =>
      L.divIcon({
        className: '',
        html: `<div class='w-7 h-7 rounded-full bg-[#2E7CF6] text-white flex items-center justify-center text-[12px] shadow-[0_0_14px_rgba(46,124,246,0.85)] border border-white/50'>${emoji}</div>`,
        iconSize: [28, 28],
      }),
    [emoji]
  );
  return <Marker position={position} icon={icon} />;
}

function CenterMap({ city }) {
  const map = useMap();
  useEffect(() => {
    if (city === 'bengaluru') {
      map.setView([12.9176, 77.6229], 14, { animate: true, duration: 0.7 });
    }
  }, [city, map]);
  return null;
}

function useAnimatedCounter(target) {
  const [value, setValue] = useState(target);
  const raf = useRef(null);
  useEffect(() => {
    const start = value;
    const duration = 400;
    let startAt;
    const frame = (t) => {
      if (!startAt) startAt = t;
      const p = Math.min(1, (t - startAt) / duration);
      setValue(Math.round(start + (target - start) * p));
      if (p < 1) raf.current = requestAnimationFrame(frame);
    };
    raf.current = requestAnimationFrame(frame);
    return () => raf.current && cancelAnimationFrame(raf.current);
  }, [target]);
  return value;
}

export default function App() {
  const [mode, setMode] = useState('replay');
  const [fleet, setFleet] = useState(initialFleet);
  const [clockSeconds, setClockSeconds] = useState(8 * 3600 + 7 * 60 + 23);
  const [timelineMinutes, setTimelineMinutes] = useState(8 * 60 + 7);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [alertSeconds, setAlertSeconds] = useState(23 * 60);
  const [overrideCards, setOverrideCards] = useState(defaultOverrides);
  const [feed, setFeed] = useState(baselineFeed);
  const [showOverrideForm, setShowOverrideForm] = useState(false);
  const [overrideReason, setOverrideReason] = useState('Insufficient demand');
  const [approved, setApproved] = useState(false);
  const [toast, setToast] = useState('');
  const [avgWait, setAvgWait] = useState(22);
  const [activeBuses, setActiveBuses] = useState(4);
  const [city, setCity] = useState('bengaluru');
  const [showPassengerDrawer, setShowPassengerDrawer] = useState(false);
  const [testAlerts, setTestAlerts] = useState([
    '08:06 — Route 500C additional dispatch sent',
    '07:58 — Alternate stop guidance sent',
    '07:47 — Delay advisory broadcast',
    '07:35 — Rain surge warning sent',
    '07:21 — Peak window advisory sent',
  ]);

  const [busProgress, setBusProgress] = useState([0.09, 0.32]);

  const [minutesSavedTarget, setMinutesSavedTarget] = useState(286);
  const [passengersServedTarget, setPassengersServedTarget] = useState(1847);
  const [dispatchesApprovedTarget, setDispatchesApprovedTarget] = useState(7);

  const minutesSaved = useAnimatedCounter(minutesSavedTarget);
  const passengersServed = useAnimatedCounter(passengersServedTarget);
  const dispatchesApproved = useAnimatedCounter(dispatchesApprovedTarget);

  const nowLabel = useMemo(() => {
    const date = new Date(2025, 3, 14, 0, 0, 0);
    const secInDay = clockSeconds % 86400;
    date.setSeconds(secInDay);
    const weekday = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][date.getDay()];
    const month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][date.getMonth()];
    return `${weekday} ${date.getDate()} ${month} ${date.getFullYear()} — ${two(date.getHours())}:${two(date.getMinutes())}:${two(
      date.getSeconds()
    )}`;
  }, [clockSeconds]);

  const busPositions = useMemo(() => busProgress.map((p) => interpolateRoute(p)), [busProgress]);

  const displayChartData = useMemo(() => {
    return chartData.map((d) => {
      const slotMinutes = Number(d.time.slice(0, 2)) * 60 + Number(d.time.slice(3));
      const actual = slotMinutes <= timelineMinutes ? d.actual : null;
      return { ...d, actualVisible: actual };
    });
  }, [timelineMinutes]);

  useEffect(() => {
    const id = setInterval(() => {
      setAlertSeconds((prev) => Math.max(0, prev - 1));
      setOverrideCards((prev) =>
        prev.map((c) => {
          if (typeof c.pendingSeconds === 'number' && c.pendingSeconds > 0) {
            const next = c.pendingSeconds - 1;
            return {
              ...c,
              pendingSeconds: next,
              badge: next > 0 ? `PENDING — Result in ${Math.floor(next / 60)}:${two(next % 60)}` : 'PENDING — Result due now',
            };
          }
          return c;
        })
      );
    }, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!playing) return;
    const interval = setInterval(() => {
      setTimelineMinutes((m) => {
        const next = m + speed;
        if (next >= 10 * 60) {
          setPlaying(false);
          return 10 * 60;
        }
        return next;
      });
      setClockSeconds((s) => s + speed * 60);
      setBusProgress((arr) => arr.map((p, i) => (p + 0.0025 * speed * (i + 1)) % 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [playing, speed]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(''), 2400);
    return () => clearTimeout(t);
  }, [toast]);

  const triggerFeed = (text, icon = '🟢') => {
    const stamp = `${formatTimeFromMinutes(timelineMinutes)} ${text}`;
    setFeed((prev) => [{ id: Date.now(), icon, text: stamp }, ...prev].slice(0, 8));
  };

  const handleDispatchFromFleet = (busId) => {
    setFleet((prev) => prev.map((b) => (b.id === busId ? { ...b, status: 'DISPATCHED' } : b)));
    setActiveBuses((n) => Math.min(12, n + 1));
    triggerFeed(`Dispatch queued — ${busId}`, '🟢');
    setToast(`Dispatch requested for ${busId}`);
  };

  const handleApprove = () => {
    if (approved) return;
    setApproved(true);
    setActiveBuses((n) => Math.min(12, n + 1));
    setAvgWait(9);
    setMinutesSavedTarget((v) => v + 18);
    setPassengersServedTarget((v) => v + 94);
    setDispatchesApprovedTarget((v) => v + 1);
    triggerFeed('Dispatch approved — KA-01-F-2234', '🟢');
    setToast('Bus KA-01-F-2234 dispatched');
  };

  const confirmOverride = () => {
    const card = {
      id: `o-${Date.now()}`,
      tone: 'neutral',
      title: `${formatTimeFromMinutes(timelineMinutes)}  —  Override: ${overrideReason}`,
      stats: '',
      badge: 'PENDING — Result in 14:00',
      note: '',
      pendingSeconds: 14 * 60,
    };
    setOverrideCards((prev) => [card, ...prev].slice(0, 3));
    setShowOverrideForm(false);
    triggerFeed(`Override logged — ${overrideReason}`, '🟡');
    setToast('Override logged');
  };

  const sendTestAlert = () => {
    const msg = `${formatTimeFromMinutes(timelineMinutes)} — Test WhatsApp alert dispatched`;
    setTestAlerts((prev) => [msg, ...prev].slice(0, 5));
    triggerFeed('Passenger test alert sent', '🔵');
    setToast('Passenger alert sent');
  };

  return (
    <div className="h-screen w-screen overflow-hidden bg-navy text-textPrimary font-sans">
      <div className="fixed inset-0 pointer-events-none opacity-[0.16] bg-[radial-gradient(circle,#9fb5d81f_1px,transparent_1px)] [background-size:18px_18px]" />

      {toast ? (
        <div className="fixed right-6 top-14 z-50 rounded-md border border-success/40 bg-success/20 px-4 py-2 text-sm text-success shadow-lg animate-slideFadeIn">
          {toast}
        </div>
      ) : null}

      <header className="h-12 border-b border-borderTone bg-panel/95 backdrop-blur fixed top-0 left-0 right-0 z-40 flex items-center px-4 gap-4">
        <div className="flex items-center gap-3 min-w-[320px]">
          <span className="text-accent font-extrabold tracking-wide text-lg">BusIQ</span>
          <span className="text-textSecondary text-sm">Silk Board Corridor — Route 500C</span>
        </div>

        <div className="flex items-center gap-2">
          {['live', 'replay', 'sim'].map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`h-8 px-3 rounded-md border text-xs uppercase tracking-wider transition-all duration-200 ${
                mode === m ? modeStyles[m] : 'border-borderTone text-textSecondary hover:text-textPrimary'
              }`}
            >
              {m} mode
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-sm text-textSecondary ml-2">
          <Clock3 className="w-4 h-4" />
          <span>{nowLabel}</span>
          <span className="w-2 h-2 rounded-full bg-accent animate-blink" />
        </div>

        <button
          onClick={() => setShowPassengerDrawer(true)}
          className="ml-auto h-8 px-3 rounded-md border border-accent/50 text-accent text-xs font-semibold hover:bg-accent/15 transition-all duration-200"
        >
          PASSENGER ALERTS
        </button>

        <div className="flex items-center gap-2 ml-2">
          <MetricChip label="AVG WAIT" value={`${avgWait} min`} color={avgWait <= 10 ? COLORS.success : COLORS.critical} />
          <MetricChip label="BUSES ACTIVE" value={`${activeBuses}/12`} color={activeBuses >= 5 ? COLORS.success : COLORS.warning} />
          <MetricChip label="ALERTS TODAY" value="3" color={COLORS.critical} />
          <MetricChip label="OVERRIDE ACC" value="84%" color={COLORS.success} />
        </div>
      </header>

      <div className="pt-12 pb-14 h-full">
        <div className="h-full flex">
          <aside className="w-[280px] border-r border-borderTone bg-panel overflow-y-auto p-3 space-y-4">
            <SectionTitle title="Fleet Status" />
            {fleet.map((bus) => (
              <div key={bus.id} className="bg-card rounded-md border border-borderTone p-2.5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm">{bus.id}</span>
                  <span className={`text-[10px] px-2 py-1 rounded border ${statusPill(bus.status)}`}>{bus.status}</span>
                </div>

                <div className="space-y-1">
                  <div className="h-1.5 rounded-full bg-[#12233b] overflow-hidden">
                    <div
                      className={`h-full ${
                        bus.shift > 55 ? 'bg-success' : bus.shift > 30 ? 'bg-warning' : 'bg-critical'
                      }`}
                      style={{ width: `${bus.shift}%` }}
                    />
                  </div>
                  <div className="text-[11px] text-textSecondary">Shift remaining {bus.shift}%</div>
                </div>

                <div>
                  <div className="text-xs text-textSecondary">Load: {bus.load[0]} / {bus.load[1]}</div>
                  <div className="h-1.5 rounded-full bg-[#12233b] overflow-hidden mt-1">
                    <div className="h-full bg-accent" style={{ width: `${(bus.load[0] / bus.load[1]) * 100}%` }} />
                  </div>
                </div>

                <div className="text-xs text-textSecondary font-mono">{bus.distance.toFixed(1)} km away</div>

                {bus.status === 'AVAILABLE' ? (
                  <button
                    onClick={() => handleDispatchFromFleet(bus.id)}
                    className="w-full text-xs h-7 rounded bg-accent/85 hover:bg-accent transition-colors duration-200"
                  >
                    DISPATCH
                  </button>
                ) : null}
              </div>
            ))}

            <SectionTitle title="Data Sources" />
            <div className="bg-card rounded-md border border-borderTone divide-y divide-borderTone/70">
              {sourceRows.map(([name, status, color]) => (
                <div key={name} className="h-7 px-2 text-xs grid grid-cols-[1fr_auto_auto] items-center gap-2">
                  <span className="text-textPrimary">{name}</span>
                  <span className="text-textSecondary">{status}</span>
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                </div>
              ))}
            </div>
          </aside>

          <main className="flex-1 p-3 grid grid-rows-[360px_1fr] gap-3 min-w-0">
            <section className="bg-panel border border-borderTone rounded-md p-2.5 relative">
              <div className="absolute top-2 left-2 z-[1000] flex items-center gap-2 bg-panel/90 border border-borderTone rounded px-2 py-1">
                <select
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="bg-transparent text-xs text-textPrimary outline-none"
                >
                  {cityOptions.map((c) => (
                    <option key={c.value} value={c.value} disabled={!c.ready}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
              <MapContainer center={[12.9176, 77.6229]} zoom={14} className="h-full w-full rounded-md z-10">
                <CenterMap city={city} />
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                <Polyline
                  positions={routePoints}
                  pathOptions={{ color: COLORS.accent, weight: 4, dashArray: '8 8', className: 'route-dash-animated' }}
                />

                {stops.map((stop) => (
                  <CircleMarker
                    key={stop.name}
                    center={stop.coords}
                    radius={loadRadius(stop.load)}
                    pathOptions={{ color: loadColor(stop.load), fillColor: loadColor(stop.load), fillOpacity: 0.65 }}
                  >
                    <Popup>
                      <div className="text-sm">
                        <div className="font-semibold">{stop.name}</div>
                        <div>Predicted load: {stop.load} pax</div>
                        <div>Next scheduled bus ETA: {stop.eta}</div>
                        <div>Last actual count: {stop.lastCount}</div>
                      </div>
                    </Popup>
                  </CircleMarker>
                ))}

                <Circle
                  center={[12.9176, 77.6229]}
                  radius={260}
                  pathOptions={{ color: COLORS.critical, fillColor: COLORS.critical, fillOpacity: 0.15, className: 'pulse-zone' }}
                />

                <AnimatedMarker position={busPositions[0]} />
                <AnimatedMarker position={busPositions[1]} />
              </MapContainer>

              {!cityOptions.find((c) => c.value === city)?.ready ? (
                <div className="absolute inset-0 z-[1100] rounded-md bg-navy/70 backdrop-blur-[1px] flex items-center justify-center">
                  <div className="bg-panel border border-borderTone rounded-md px-4 py-2 text-sm text-textSecondary">
                    Calibrating data for {city === 'chennai' ? 'Chennai' : city === 'pune' ? 'Pune' : 'Hyderabad'}... Est. 8 days onboarding
                  </div>
                </div>
              ) : null}
            </section>

            <section className="bg-panel border border-borderTone rounded-md p-3 flex flex-col min-h-0">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-sm font-semibold tracking-wide">DEMAND FORECAST — Silk Board Junction</h2>
                <span className="text-xs px-2 py-1 border border-success/40 text-success rounded">MODEL MAE: 9.4 pax</span>
              </div>
              <div className="h-[220px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={displayChartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="predFill" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stopColor={COLORS.accent} stopOpacity={0.3} />
                        <stop offset="100%" stopColor={COLORS.accent} stopOpacity={0.02} />
                      </linearGradient>
                      <linearGradient id="actFill" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stopColor={COLORS.success} stopOpacity={0.22} />
                        <stop offset="100%" stopColor={COLORS.success} stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke={COLORS.border} strokeDasharray="3 3" />
                    <XAxis dataKey="time" stroke={COLORS.textSecondary} tick={{ fill: COLORS.textSecondary, fontSize: 11 }} />
                    <YAxis stroke={COLORS.textSecondary} tick={{ fill: COLORS.textSecondary, fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ background: COLORS.panel, border: `1px solid ${COLORS.border}`, color: COLORS.textPrimary }}
                    />
                    <ReferenceLine x={formatTimeFromMinutes(timelineMinutes)} stroke={COLORS.critical} strokeDasharray="6 6" label="NOW" />
                    <ReferenceLine y={350} stroke={COLORS.warning} strokeDasharray="6 6" label="DISPATCH THRESHOLD" />
                    <Area type="monotone" dataKey="predicted" stroke={COLORS.accent} fill="url(#predFill)" strokeWidth={2} />
                    <Area type="monotone" dataKey="actualVisible" stroke={COLORS.success} fill="url(#actFill)" strokeWidth={2} />
                    <Line type="monotone" dataKey="predicted" stroke={COLORS.accent} strokeDasharray="3 4" dot={false} opacity={0.5} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <div className="grid grid-cols-13 gap-1 mt-2">
                {chartData.map((d) => {
                  const tone = d.predicted > 300 ? 'bg-critical/30 border-critical/60' : d.predicted > 100 ? 'bg-warning/25 border-warning/50' : 'bg-success/25 border-success/45';
                  const enlarged = d.time === '08:15';
                  return (
                    <div
                      key={d.time}
                      className={`rounded border px-1 py-1 text-center ${tone} ${enlarged ? 'scale-105 shadow-critical' : ''} transition-transform duration-200`}
                    >
                      <div className="text-[10px] text-textSecondary">{d.time}</div>
                      <div className="text-[11px] font-semibold font-mono">{d.predicted}</div>
                    </div>
                  );
                })}
              </div>
            </section>
          </main>

          <aside className="w-[320px] border-l border-borderTone bg-panel p-3 overflow-y-auto space-y-3">
            <section className="bg-card border border-critical/40 border-l-4 border-l-critical shadow-critical rounded-md p-3 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs px-2 py-1 rounded bg-critical/20 text-critical animate-blink">⚠ SURGE ALERT</span>
                <span className="text-xs px-2 py-1 rounded border border-warning/50 text-warning">
                  {Math.floor(alertSeconds / 60)}:{two(alertSeconds % 60)} lead time
                </span>
              </div>

              <div>
                <div className="text-xs text-textSecondary">Stop</div>
                <div className="text-sm font-semibold">Silk Board Junction</div>
                <div className="text-critical text-2xl font-bold mt-1">487 passengers</div>
                <div className="text-xs text-textSecondary">08:15 — 08:30</div>
                <div className="mt-2 text-xs text-textSecondary">Confidence: 81%</div>
                <div className="h-1.5 rounded-full bg-navy mt-1 overflow-hidden"><div className="h-full bg-success" style={{ width: '81%' }} /></div>
              </div>

              <div className="bg-navy/35 border border-borderTone rounded-md p-2.5">
                <div className="text-[11px] uppercase tracking-wider text-textSecondary mb-2">Why This Alert Fired</div>
                <ShapBar label="Monday morning peak" value={38} />
                <ShapBar label="Heavy rainfall" value={29} />
                <ShapBar label="Metro Line 1 delay" value={18} />
                <p className="text-xs text-textSecondary mt-2">
                  Rain on a Monday with Metro disruption historically causes 340% above-baseline demand at this stop.
                </p>
              </div>

              <div className="bg-navy/40 border border-borderTone rounded-md p-2.5 space-y-2">
                <div className="text-[11px] uppercase tracking-wider text-textSecondary">Recommended Dispatch</div>
                <div className="font-mono text-lg">KA-01-F-2234</div>
                <div className="text-xs text-textSecondary">ETA to stop: 12 minutes</div>
                <div className="text-xs text-textSecondary">Shift remaining: 6.5 hours</div>
                <div className="text-xs text-textSecondary">Route: Via Bommanahalli → Silk Board</div>

                <button
                  onClick={handleApprove}
                  className={`w-full h-11 rounded text-sm font-bold transition-all duration-200 ${
                    approved ? 'bg-success text-navy' : 'bg-accent hover:bg-accent/90'
                  }`}
                >
                  {approved ? '✓ Dispatched at 08:09' : '✓ APPROVE DISPATCH'}
                </button>

                <button
                  onClick={() => setShowOverrideForm((v) => !v)}
                  className="w-full h-11 rounded border border-critical text-critical hover:bg-critical/10 transition-all duration-200 text-sm font-semibold"
                >
                  ✗ OVERRIDE
                </button>

                {showOverrideForm ? (
                  <div className="space-y-2">
                    <select
                      value={overrideReason}
                      onChange={(e) => setOverrideReason(e.target.value)}
                      className="w-full h-9 rounded bg-panel border border-borderTone text-sm px-2"
                    >
                      <option>Insufficient demand</option>
                      <option>Bus needed elsewhere</option>
                      <option>Driver unavailable</option>
                      <option>Other</option>
                    </select>
                    <button onClick={confirmOverride} className="w-full h-9 rounded bg-critical text-sm font-semibold">
                      CONFIRM OVERRIDE
                    </button>
                  </div>
                ) : null}
              </div>
            </section>

            <section className="space-y-2">
              <SectionTitle title="Override Outcomes" subtitle="System accuracy when overridden: 84%" />
              {overrideCards.map((card) => (
                <div
                  key={card.id}
                  className={`rounded-md border p-2.5 ${
                    card.tone === 'red'
                      ? 'bg-critical/10 border-critical/30'
                      : card.tone === 'green'
                      ? 'bg-success/10 border-success/30'
                      : 'bg-card border-borderTone'
                  }`}
                >
                  <div className="text-xs text-textPrimary">{card.title}</div>
                  {card.stats ? <div className="text-[11px] text-textSecondary mt-1">{card.stats}</div> : null}
                  <div
                    className={`text-[11px] mt-1 inline-flex px-2 py-1 rounded border ${
                      card.tone === 'red'
                        ? 'text-critical border-critical/50'
                        : card.tone === 'green'
                        ? 'text-success border-success/50'
                        : 'text-warning border-warning/50'
                    }`}
                  >
                    {card.badge}
                  </div>
                  {card.note ? <div className="text-[11px] text-textSecondary mt-1">{card.note}</div> : null}
                </div>
              ))}
            </section>

            <section>
              <SectionTitle title="Live Feed" />
              <div className="rounded-md border border-borderTone bg-card max-h-[250px] overflow-y-auto divide-y divide-borderTone/60">
                {feed.map((event) => (
                  <div key={event.id} className="h-8 px-2 text-xs flex items-center gap-2 animate-slideFadeIn">
                    <span>{event.icon}</span>
                    <span className="text-textSecondary">{event.text}</span>
                  </div>
                ))}
              </div>
            </section>
          </aside>
        </div>
      </div>

      <footer className="h-14 border-t border-borderTone fixed bottom-0 left-0 right-0 bg-panel/95 backdrop-blur px-4 flex items-center justify-between z-40">
        <div className="flex items-center gap-3 min-w-[420px]">
          <span className="text-xs text-textSecondary uppercase tracking-wider">Simulation Controls</span>
          <button
            onClick={() => setPlaying((v) => !v)}
            className="h-8 w-8 rounded border border-borderTone flex items-center justify-center hover:border-accent transition-colors duration-200"
          >
            {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </button>
          <div className="flex items-center gap-1">
            {[1, 2, 5].map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={`h-7 px-2 rounded text-xs border transition-all duration-200 ${
                  speed === s ? 'border-accent text-accent bg-accent/10' : 'border-borderTone text-textSecondary'
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
          <input
            type="range"
            min={7 * 60}
            max={10 * 60}
            value={timelineMinutes}
            onChange={(e) => {
              const val = Number(e.target.value);
              setTimelineMinutes(val);
              setClockSeconds(14 * 3600 + val * 60 + 23);
            }}
            className="w-56"
          />
          <span className="text-xs text-textSecondary font-mono">{formatTimeFromMinutes(timelineMinutes)}</span>
        </div>

        <div className="flex items-center gap-8">
          <Kpi label="MINUTES SAVED TODAY" value={minutesSaved} />
          <Kpi label="PASSENGERS SERVED" value={passengersServed} />
          <Kpi label="DISPATCHES APPROVED" value={dispatchesApproved} />
        </div>

        <div className="flex items-center gap-2 min-w-[250px] justify-end">
          <span className="text-xs text-textSecondary uppercase">Model Performance</span>
          <span className="text-xs px-2 py-1 rounded border border-success/40 text-success">30-DAY MAE 9.4 pax</span>
          <span className="text-xs px-2 py-1 rounded border border-accent/40 text-accent">LAST RETRAIN 08:01 AM</span>
        </div>
      </footer>

      {showPassengerDrawer ? (
        <div className="fixed top-12 bottom-14 right-0 w-[320px] bg-panel border-l border-borderTone z-50 p-3 animate-slideFadeIn">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold">Passenger Alerts</h3>
            <button onClick={() => setShowPassengerDrawer(false)} className="p-1 hover:bg-card rounded">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="mx-auto w-[210px] h-[430px] rounded-[26px] border border-borderTone bg-navy p-3 shadow-xl">
            <div className="w-14 h-1 rounded-full bg-borderTone mx-auto mb-3" />
            <div className="bg-success/20 border border-success/40 rounded-xl p-2 text-[12px] leading-5 text-textPrimary">
              🚌 BusIQ Alert
              <br />
              Extra Route 500C arriving Silk Board Junction in 12 min.
              <br />
              Alternate: Walk 200m to HSR 8th Cross stop — Route 335C in 6 min.
              <br />— BusIQ Dispatch System
            </div>
          </div>

          <button onClick={sendTestAlert} className="w-full h-10 mt-3 rounded bg-success text-navy font-semibold flex items-center justify-center gap-2">
            <Send className="w-4 h-4" /> SEND TEST ALERT
          </button>

          <div className="mt-3 space-y-1">
            {testAlerts.map((a, idx) => (
              <div key={`${a}-${idx}`} className="text-xs text-textSecondary border border-borderTone rounded p-1.5">
                {a}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function SectionTitle({ title, subtitle }) {
  return (
    <div className="space-y-0.5">
      <div className="text-[11px] uppercase tracking-wider text-textSecondary font-semibold">{title}</div>
      {subtitle ? <div className="text-[11px] text-textSecondary">{subtitle}</div> : null}
    </div>
  );
}

function MetricChip({ label, value, color }) {
  return (
    <div className="h-7 px-2 rounded-full border border-borderTone flex items-center gap-1.5 text-[11px]" style={{ color }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
      <span>{label}</span>
      <span className="font-semibold">{value}</span>
    </div>
  );
}

function ShapBar({ label, value }) {
  return (
    <div className="mb-2">
      <div className="flex items-center justify-between text-[11px] text-textSecondary">
        <span>{label}</span>
        <span>+{value}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-panel mt-1 overflow-hidden">
        <div className="h-full bg-accent" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function Kpi({ label, value }) {
  return (
    <div className="text-center">
      <div className="text-[10px] text-textSecondary tracking-wider">{label}</div>
      <div className="font-mono text-base font-semibold">{value.toLocaleString()}</div>
    </div>
  );
}
