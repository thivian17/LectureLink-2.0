import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default withSentryConfig(nextConfig, {
  org: "lecturelink",
  project: "lecturelink-web",
  silent: true,
  widenClientFileUpload: true,
  sourcemaps: {
    disable: true,
  },
});
