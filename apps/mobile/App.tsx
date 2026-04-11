import RootNavigator from "./src/app/navigation/RootNavigator";

(globalThis as { __AI_STORE_MANAGER_ENABLE_DEV_TOOLS__?: boolean }).__AI_STORE_MANAGER_ENABLE_DEV_TOOLS__ =
  process.env.EXPO_PUBLIC_ENABLE_DEV_TOOLS === "true";

export default function App() {
  return <RootNavigator />;
}
