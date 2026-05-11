import type { NextConfig } from "next";

const distDir = process.env.NEXT_DIST_DIR?.trim() || ".next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  compress: true,
  distDir,
  output: "standalone",
};

export default nextConfig;
