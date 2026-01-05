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
    // Disable CSS optimization to allow PostCSS processing
    optimizeCss: false,
  },
  // Allow cross-origin requests from hostname in development mode
  // This is needed when accessing the console via hostname (e.g., rpdgxspark:3000)
  allowedDevOrigins: ['rpdgxspark', 'localhost', '127.0.0.1'],
  // Enable standalone output for optimized Docker builds (Compose-First deployment)
  // Note: Disabled in dev mode to avoid CSS processing issues
  // output: 'standalone',
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
  webpack: (config, { isServer }) => {
    config.resolve = config.resolve || {};
    config.resolve.fallback = {
      ...(config.resolve.fallback || {}),
      canvas: false,
    };
    
    // Fix for Next.js 15 CSS processing: Ensure PostCSS runs before flight CSS loader
    if (!isServer) {
      const cssRule = config.module.rules.find(
        (rule) => rule.test && rule.test.toString().includes('css')
      );
      
      if (cssRule) {
        // Find the flight CSS loader and ensure PostCSS runs first
        const oneOfRule = config.module.rules.find(
          (rule) => rule.oneOf
        );
        
        if (oneOfRule && oneOfRule.oneOf) {
          oneOfRule.oneOf.forEach((rule) => {
            if (rule.test && rule.test.toString().includes('css')) {
              // Ensure PostCSS loader is in the chain
              if (rule.use && Array.isArray(rule.use)) {
                const hasPostCSS = rule.use.some(
                  (loader) => loader && (loader.loader?.includes('postcss') || loader === 'postcss-loader')
                );
                if (!hasPostCSS) {
                  rule.use.unshift({
                    loader: 'postcss-loader',
                    options: {
                      postcssOptions: {
                        plugins: {
                          tailwindcss: {},
                          autoprefixer: {},
                        },
                      },
                    },
                  });
                }
              }
            }
          });
        }
      }
    }
    
    return config;
  },
}

// Define environment variables that should be available to the client
const clientEnv = {
  NVIDIA_API_KEY: process.env.NVIDIA_API_KEY,
  // Other environment variables as needed
};

export default nextConfig
