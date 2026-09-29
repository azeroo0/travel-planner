import type { NextConfig } from 'next';

const backend = process.env.API_SERVER_URL?.replace(/\/$/, '');

const nextConfig: NextConfig = {
  distDir: process.env.NODE_ENV === 'development' ? '.next-dev' : '.next',
  async rewrites() {
    return backend ? [{ source: '/api/:path*', destination: `${backend}/api/:path*` }] : [];
  },
};

export default nextConfig;
