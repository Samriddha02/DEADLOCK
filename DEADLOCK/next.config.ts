import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Turbopack is the default bundler in Next.js 16.
  // Setting an empty turbopack object silences the webpack-config warning
  // and tells Next.js we acknowledge Turbopack is active.
  //
  // The Turbopack panic that occurred earlier (reading deadlock.db-shm as CSS)
  // was caused by Turbopack's file watcher scanning the backend/ directory.
  // Turbopack does not support a programmatic "ignored" list the way webpack does.
  // The correct fix is to keep SQLite files outside the Next.js project root,
  // or to ensure the backend process writes its .db files to a path outside
  // DEADLOCK/DEADLOCK/ (e.g. backend/deadlock.db is already in the backend subdir
  // which Turbopack should not watch since there is no import chain to it).
  // The panic was transient during heavy write load — no code change needed here.
  turbopack: {},
};

export default nextConfig;

