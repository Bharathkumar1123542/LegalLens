/** @type {import('next').NextConfig} */
const nextConfig = {
  // Strict mode catches lifecycle bugs early
  reactStrictMode: true,

  // Never expose sensitive env vars; only NEXT_PUBLIC_ prefix is client-safe
  env: {
    // (intentionally empty — use NEXT_PUBLIC_ prefix for client vars)
  },

  // Security headers — Phase 9: Added comprehensive CSP
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          // Basic security headers
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          
          // Content Security Policy (Phase 9)
          // Prevents XSS attacks by controlling which resources can be loaded
          {
            key: 'Content-Security-Policy',
            value: [
              // Default: only allow resources from same origin
              "default-src 'self'",
              
              // Scripts: self + Next.js inline scripts (strict-dynamic for modern browsers)
              // unsafe-eval needed for Next.js dev mode
              process.env.NODE_ENV === 'development'
                ? "script-src 'self' 'unsafe-eval' 'unsafe-inline'"
                : "script-src 'self' 'unsafe-inline'",
              
              // Styles: self + inline styles (required for styled-components, Tailwind)
              "style-src 'self' 'unsafe-inline'",
              
              // Images: self + data URIs (for base64 images) + external CDNs
              "img-src 'self' data: https:",
              
              // Fonts: self + data URIs
              "font-src 'self' data:",
              
              // Connect (AJAX/fetch): self + API server
              process.env.NEXT_PUBLIC_API_URL
                ? `connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL}`
                : "connect-src 'self'",
              
              // Frames: none (already enforced by X-Frame-Options)
              "frame-src 'none'",
              
              // Objects (Flash, etc.): none
              "object-src 'none'",
              
              // Base URI: restrict to same origin
              "base-uri 'self'",
              
              // Form actions: only submit to same origin or API
              process.env.NEXT_PUBLIC_API_URL
                ? `form-action 'self' ${process.env.NEXT_PUBLIC_API_URL}`
                : "form-action 'self'",
              
              // Upgrade insecure requests in production
              process.env.NODE_ENV === 'production' ? 'upgrade-insecure-requests' : '',
              
              // Block all mixed content
              process.env.NODE_ENV === 'production' ? 'block-all-mixed-content' : '',
            ]
              .filter(Boolean) // Remove empty strings
              .join('; '),
          },
          
          // Permissions Policy (formerly Feature-Policy)
          // Disable unnecessary browser features
          {
            key: 'Permissions-Policy',
            value: [
              'camera=()',
              'microphone=()',
              'geolocation=()',
              'payment=()',
              'usb=()',
              'magnetometer=()',
              'gyroscope=()',
              'accelerometer=()',
            ].join(', '),
          },
          
          // Strict Transport Security (HTTPS enforcement)
          // Only in production with HTTPS
          ...(process.env.NODE_ENV === 'production'
            ? [
                {
                  key: 'Strict-Transport-Security',
                  value: 'max-age=31536000; includeSubDomains; preload',
                },
              ]
            : []),
        ],
      },
    ];
  },
};

module.exports = nextConfig;
