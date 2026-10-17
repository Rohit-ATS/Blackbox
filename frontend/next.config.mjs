/** @type {import('next').NextConfig} */

// GitHub Pages serves static files from a project subpath, so the Pages build
// sets NEXT_PUBLIC_REPLAY=1 and NEXT_PUBLIC_BASE_PATH=/<repo>. Locally and in
// Docker both are unset, and the app talks to the live backend as normal.
const isExport = process.env.NEXT_PUBLIC_REPLAY === "1";
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
  },
};

export default nextConfig;
