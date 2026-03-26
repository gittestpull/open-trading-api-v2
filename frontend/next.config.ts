import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://trading-web:8080/api/:path*",
      },
      {
        source: "/ws/:path*",
        destination: "http://trading-web:8080/ws/:path*",
      },
    ];
  },
};

export default nextConfig;
