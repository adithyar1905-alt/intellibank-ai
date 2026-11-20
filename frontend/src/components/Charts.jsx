import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { monthlyData } from "../data/demo.js";

const axis = { stroke: "#8a96a8", fontSize: 11 };

export function VolumeChart({ data = monthlyData }) {
  return <div className="chart-frame"><ResponsiveContainer width="100%" height="100%">
    <AreaChart data={data} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
      <defs><linearGradient id="volumeFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#0d9488" stopOpacity={0.22} /><stop offset="100%" stopColor="#0d9488" stopOpacity={0} /></linearGradient></defs>
      <CartesianGrid stroke="#edf0f4" vertical={false} />
      <XAxis dataKey="month" tick={axis} axisLine={false} tickLine={false} />
      <YAxis tick={axis} axisLine={false} tickLine={false} />
      <Tooltip />
      <Area type="monotone" dataKey="transactions" name="Volume ($M)" stroke="#0d9488" strokeWidth={2.5} fill="url(#volumeFill)" />
    </AreaChart>
  </ResponsiveContainer></div>;
}

export function DepositChart({ data = monthlyData }) {
  return <div className="chart-frame"><ResponsiveContainer width="100%" height="100%">
    <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
      <CartesianGrid stroke="#edf0f4" vertical={false} />
      <XAxis dataKey="month" tick={axis} axisLine={false} tickLine={false} />
      <YAxis tick={axis} axisLine={false} tickLine={false} />
      <Tooltip />
      <Bar dataKey="deposits" name="Deposits" fill="#0d9488" radius={[4, 4, 0, 0]} />
      <Bar dataKey="withdrawals" name="Withdrawals" fill="#b9c9d8" radius={[4, 4, 0, 0]} />
    </BarChart>
  </ResponsiveContainer></div>;
}

export function GrowthChart({ data = monthlyData }) {
  return <div className="chart-frame"><ResponsiveContainer width="100%" height="100%">
    <LineChart data={data} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
      <CartesianGrid stroke="#edf0f4" vertical={false} />
      <XAxis dataKey="month" tick={axis} axisLine={false} tickLine={false} />
      <YAxis tick={axis} axisLine={false} tickLine={false} />
      <Tooltip />
      <Line type="monotone" dataKey="customers" name="Customers" stroke="#3158a5" strokeWidth={2.5} dot={{ r: 3, fill: "#3158a5" }} />
    </LineChart>
  </ResponsiveContainer></div>;
}

export function RiskChart({ data = [{ name: "Low", value: 38 }, { name: "Medium", value: 27 }, { name: "High", value: 23 }, { name: "Critical", value: 12 }] }) {
  const colors = ["#0d9488", "#eab308", "#f97316", "#dc4d59"];
  return <div className="chart-frame"><ResponsiveContainer width="100%" height="100%">
    <PieChart><Tooltip /><Pie data={data} dataKey="value" nameKey="name" innerRadius="58%" outerRadius="82%" paddingAngle={4}>
      {data.map((entry, index) => <Cell key={entry.name} fill={colors[index % colors.length]} />)}
    </Pie></PieChart>
  </ResponsiveContainer></div>;
}
