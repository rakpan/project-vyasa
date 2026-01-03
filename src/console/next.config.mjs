/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  // Reposition dev indicator to avoid sidebar overlap
  devIndicators: {
    position: 'top-right',
  },
  // Configure external packages for server components
  serverExternalPackages: ['@langchain/community'],
  experimental: {
    // webpackBuildWorker: true,
  },
  // Enable standalone output for optimized Docker builds (Compose-First deployment)
  output: 'standalone',
  // Make environment variables accessible to server components
  env: {
    NVIDIA_API_KEY: process.env.NVIDIA_API_KEY,
  },
  // Remove API route timeout limits for large model processing
  serverRuntimeConfig: {
    // No duration limit - let large models complete naturally
    maxDuration: 0,
  },
  // Avoid installing native canvas for pdfjs-dist (@react-pdf-viewer) during SSR bundling
  webpack: (config) => {
    config.resolve = config.resolve || {};
    config.resolve.fallback = {
      ...(config.resolve.fallback || {}),
      canvas: false,
    };
    return config;
  },
}

// Define environment variables that should be available to the client
const clientEnv = {
  NVIDIA_API_KEY: process.env.NVIDIA_API_KEY,
  // Other environment variables as needed
};

export default nextConfig
