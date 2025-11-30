"use client";

import { X, BarChart3, PieChart, AlertTriangle, Activity } from "lucide-react";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart as RePieChart, Pie, Cell
} from "recharts";
import { Asset } from "@/types";
import { motion } from "framer-motion";
import clsx from "clsx";

interface RiskDashboardProps {
  assets: Asset[];
  onClose: () => void;
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

export default function RiskDashboard({ assets, onClose }: RiskDashboardProps) {
  // Process data for charts
  
  // 1. Risk by Province
  const provinceData = assets.reduce((acc: any, asset) => {
    const prov = asset.province;
    const score = asset.risk_scores?.length > 0 ? asset.risk_scores[asset.risk_scores.length - 1].overall_score : 0;
    
    if (!acc[prov]) {
      acc[prov] = { name: prov, totalRisk: 0, count: 0, avgRisk: 0 };
    }
    acc[prov].totalRisk += score;
    acc[prov].count += 1;
    acc[prov].avgRisk = acc[prov].totalRisk / acc[prov].count;
    return acc;
  }, {});
  
  const barChartData = Object.values(provinceData).map((d: any) => ({
    name: d.name.replace("Newfoundland and Labrador", "NL").replace("Prince Edward Island", "PEI").replace("Nova Scotia", "NS").replace("New Brunswick", "NB"),
    "Average Risk": parseFloat(d.avgRisk.toFixed(1))
  }));

  // 2. Asset Type Distribution
  const typeData = assets.reduce((acc: any, asset) => {
    const type = asset.type;
    if (!acc[type]) acc[type] = 0;
    acc[type] += 1;
    return acc;
  }, {});

  const pieChartData = Object.keys(typeData).map(key => ({
    name: key.charAt(0).toUpperCase() + key.slice(1),
    value: typeData[key]
  }));

  // 3. Risk Distribution
  const riskDist = [
    { name: "Low", value: assets.filter(a => {
      const s = a.risk_scores?.length > 0 ? a.risk_scores[a.risk_scores.length - 1].overall_score : 0;
      return s < 25;
    }).length, color: '#10b981' },
    { name: "Medium", value: assets.filter(a => {
      const s = a.risk_scores?.length > 0 ? a.risk_scores[a.risk_scores.length - 1].overall_score : 0; 
      return s >= 25 && s < 50;
    }).length, color: '#facc15' },
    { name: "High", value: assets.filter(a => {
      const s = a.risk_scores?.length > 0 ? a.risk_scores[a.risk_scores.length - 1].overall_score : 0; 
      return s >= 50 && s < 75;
    }).length, color: '#f97316' },
    { name: "Critical", value: assets.filter(a => {
      const s = a.risk_scores?.length > 0 ? a.risk_scores[a.risk_scores.length - 1].overall_score : 0;
      return s >= 75;
    }).length, color: '#ef4444' },
  ];

  const criticalCount = assets.filter(a => (a.risk_scores?.length > 0 ? (a.risk_scores[a.risk_scores.length-1]?.overall_score || 0) : 0) >= 75).length;
  const avgRisk = assets.reduce((acc, a) => acc + (a.risk_scores?.length > 0 ? (a.risk_scores[a.risk_scores.length-1]?.overall_score || 0) : 0), 0) / assets.length;

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center z-[2000] p-4">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="bg-slate-50 rounded-2xl shadow-2xl w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col border border-slate-200"
      >
        {/* Header */}
        <div className="p-6 border-b border-slate-200 flex justify-between items-center bg-white">
          <div className="flex items-center gap-3">
             <div className="p-2 bg-indigo-100 text-indigo-700 rounded-lg">
               <Activity size={24} />
             </div>
             <div>
               <h2 className="text-xl font-bold text-slate-900">Risk Intelligence Dashboard</h2>
               <p className="text-sm text-slate-500">Real-time infrastructure analytics</p>
             </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full text-slate-400 hover:text-slate-600 transition-colors">
            <X size={24} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {/* Bento Grid Layout */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
            {/* KPI Cards */}
            <KPICard 
              label="Total Assets" 
              value={assets.length} 
              icon={<BarChart3 size={20} />}
              trend="+12% vs last year"
            />
            <KPICard 
              label="Critical Assets" 
              value={criticalCount} 
              icon={<AlertTriangle size={20} />}
              color="text-red-600"
              bg="bg-red-50"
              trend="Requires attention"
            />
            <KPICard 
              label="Average Risk" 
              value={avgRisk.toFixed(1)} 
              icon={<Activity size={20} />}
              color="text-blue-600"
              bg="bg-blue-50"
            />
             <KPICard 
              label="Data Freshness" 
              value="98%" 
              icon={<PieChart size={20} />}
              color="text-green-600"
              bg="bg-green-50"
              trend="Updated today"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
             {/* Charts */}
             <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 col-span-1 lg:col-span-2">
                <h3 className="font-bold text-slate-800 mb-6 flex items-center gap-2">
                  <BarChart3 size={18} className="text-slate-400" /> Regional Risk Profile
                </h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={barChartData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 12}} dy={10} />
                      <YAxis axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 12}} />
                      <Tooltip 
                        contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                        cursor={{fill: '#f8fafc'}}
                      />
                      <Bar dataKey="Average Risk" fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={40} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
             </div>

             <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                <h3 className="font-bold text-slate-800 mb-6 flex items-center gap-2">
                  <PieChart size={18} className="text-slate-400" /> Asset Mix
                </h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <RePieChart>
                      <Pie
                        data={pieChartData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {pieChartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} stroke="none" />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}} />
                      <Legend verticalAlign="bottom" height={36} iconType="circle" />
                    </RePieChart>
                  </ResponsiveContainer>
                </div>
             </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
             {/* Risk Distribution Bar */}
             <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                <h3 className="font-bold text-slate-800 mb-6">Risk Severity</h3>
                <div className="space-y-4">
                  {riskDist.map((item) => (
                    <div key={item.name} className="space-y-1">
                      <div className="flex justify-between text-sm">
                        <span className="font-medium text-slate-600">{item.name}</span>
                        <span className="font-bold text-slate-900">{item.value}</span>
                      </div>
                      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                        <motion.div 
                          initial={{ width: 0 }}
                          animate={{ width: `${(item.value / assets.length) * 100}%` }}
                          className="h-full rounded-full"
                          style={{ backgroundColor: item.color }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
             </div>

             {/* Top Critical Assets Table */}
             <div className="bg-white rounded-2xl shadow-sm border border-slate-200 col-span-1 md:col-span-2 overflow-hidden flex flex-col">
                <div className="p-6 border-b border-slate-100">
                  <h3 className="font-bold text-slate-800">Critical Attention Required</h3>
                </div>
                <div className="flex-1 overflow-auto">
                  <table className="w-full text-sm text-left">
                    <thead className="bg-slate-50 text-slate-500 font-medium">
                      <tr>
                        <th className="p-4 pl-6">Asset Name</th>
                        <th className="p-4">Type</th>
                        <th className="p-4">Province</th>
                        <th className="p-4 text-right pr-6">Risk Score</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {assets
                        .sort((a, b) => {
                          const scoreA = a.risk_scores?.length > 0 ? a.risk_scores[a.risk_scores.length - 1].overall_score : 0;
                          const scoreB = b.risk_scores?.length > 0 ? b.risk_scores[b.risk_scores.length - 1].overall_score : 0;
                          return scoreB - scoreA;
                        })
                        .slice(0, 5)
                        .map((asset) => {
                          const score = asset.risk_scores?.length > 0 ? asset.risk_scores[asset.risk_scores.length - 1].overall_score : 0;
                          return (
                            <tr key={asset.id} className="hover:bg-slate-50/50 transition-colors">
                              <td className="p-4 pl-6 font-medium text-slate-900">{asset.name}</td>
                              <td className="p-4 text-slate-500 capitalize">{asset.type}</td>
                              <td className="p-4 text-slate-500">{asset.province}</td>
                              <td className="p-4 text-right pr-6">
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                                  {score.toFixed(1)}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
             </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

function KPICard({ label, value, icon, color, bg, trend }: any) {
  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
      <div className="flex justify-between items-start mb-4">
        <div className={clsx("p-2 rounded-lg", bg ? bg : "bg-slate-100", color ? color : "text-slate-600")}>
          {icon}
        </div>
        {trend && <span className="text-[10px] font-medium text-green-600 bg-green-50 px-2 py-1 rounded-full">{trend}</span>}
      </div>
      <div>
        <h4 className="text-3xl font-bold text-slate-900 tracking-tight">{value}</h4>
        <p className="text-sm text-slate-500 font-medium mt-1">{label}</p>
      </div>
    </div>
  );
}
