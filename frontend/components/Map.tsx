"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { Asset } from "@/types"; // We'll define this type
import axios from "axios";

// Fix for default marker icon in Leaflet with Next.js
const iconUrl = "https://unpkg.com/leaflet@1.9.3/dist/images/marker-icon.png";
const iconRetinaUrl = "https://unpkg.com/leaflet@1.9.3/dist/images/marker-icon-2x.png";
const shadowUrl = "https://unpkg.com/leaflet@1.9.3/dist/images/marker-shadow.png";

const defaultIcon = L.icon({
  iconUrl,
  iconRetinaUrl,
  shadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

// Custom colored icons based on risk
const getIcon = (riskScore: number) => {
    let colorClass = "bg-green-500";
    if (riskScore >= 75) colorClass = "bg-red-600";
    else if (riskScore >= 50) colorClass = "bg-orange-500";
    else if (riskScore >= 25) colorClass = "bg-yellow-400";

    return L.divIcon({
      className: "custom-marker",
      html: `<div class="${colorClass} w-4 h-4 rounded-full border-2 border-white shadow-md"></div>`,
      iconSize: [16, 16],
      iconAnchor: [8, 8],
      popupAnchor: [0, -10],
    });
};

export default function Map({ assets }: { assets: Asset[] }) {
  // Fix for default marker icon in Leaflet with Next.js
  // (We need to ensure this runs only on client, which it does since this component is dynamic ssr:false)
  
  return (
    <MapContainer
      center={[46.5, -63.5]} // Atlantic Canada center
      zoom={6}
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {assets.map((asset) => {
          // Get latest risk score
          const riskScore = asset.risk_scores?.length > 0 ? asset.risk_scores[asset.risk_scores.length - 1].overall_score : 0;
          
          return (
            <Marker 
                key={asset.id} 
                position={[asset.latitude, asset.longitude]}
                icon={getIcon(riskScore)}
            >
              <Popup>
                <div className="p-2">
                  <h3 className="font-bold text-lg">{asset.name}</h3>
                  <p className="text-sm text-gray-600">{asset.type} • {asset.province}</p>
                  <div className="mt-2">
                    <span className={`font-bold ${riskScore >= 75 ? 'text-red-600' : riskScore >= 50 ? 'text-orange-500' : 'text-green-600'}`}>
                        Risk Score: {riskScore.toFixed(1)}
                    </span>
                  </div>
                  <p className="text-xs mt-1">Daily Usage: {asset.daily_usage?.toLocaleString()}</p>
                </div>
              </Popup>
            </Marker>
          );
      })}
    </MapContainer>
  );
}
