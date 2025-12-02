import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Disable image optimization for Docker (or configure external loader)
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
