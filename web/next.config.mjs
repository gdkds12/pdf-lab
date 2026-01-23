/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'standalone',
    experimental: {
        serverComponentsExternalPackages: ['@google-cloud/run', '@google-cloud/storage', 'google-auth-library'],
    }
};

export default nextConfig;
