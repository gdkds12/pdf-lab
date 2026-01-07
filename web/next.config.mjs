/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'standalone',
    serverExternalPackages: ['@google-cloud/run', '@google-cloud/storage', 'google-auth-library'],
};

export default nextConfig;
