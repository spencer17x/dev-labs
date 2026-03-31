import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Allow local dev access from both localhost and 127.0.0.1 so client assets
  // hydrate correctly when the app is opened via either address.
  allowedDevOrigins: ['localhost', '127.0.0.1'],
};

export default nextConfig;
