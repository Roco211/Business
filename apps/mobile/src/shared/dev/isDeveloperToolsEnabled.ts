export function isDeveloperToolsEnabled(): boolean {
  return (
    process.env.NODE_ENV !== "production"
    && Boolean(
      (globalThis as { __AI_STORE_MANAGER_ENABLE_DEV_TOOLS__?: boolean })
        .__AI_STORE_MANAGER_ENABLE_DEV_TOOLS__,
    )
  );
}
