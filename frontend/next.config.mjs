/** @type {import('next').NextConfig} */

// GitHub Pages serves static files from a project subpath. Keep export mode
// separate from replay mode so Pages can call the live Render backend.
const isExport = process.env.NEXT_PUBLIC_PAGES === "1";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const nextConfig = {
  reactStrictMode: true,
  ...(isExport
    ? {
        output: "export",
        basePath,
        assetPrefix: basePath || undefined,
        images: { unoptimized: true },
        trailingSlash: true,
      }
    : {}),
  env: {
    NEXT_PUBLIC_BACKEND_URL:
      process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000",
    NEXT_PUBLIC_BASE_PATH: basePath,
    NEXT_PUBLIC_REPLAY: process.env.NEXT_PUBLIC_REPLAY ?? "",
    NEXT_PUBLIC_PAGES: process.env.NEXT_PUBLIC_PAGES ?? "",
  },
};

export default nextConfig;
