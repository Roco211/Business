import { inferDevServerHost, resolveApiBaseUrl } from "../resolveApiBaseUrl";

describe("resolveApiBaseUrl", () => {
  it("uses EXPO_PUBLIC_API_BASE_URL when provided", () => {
    expect(
      resolveApiBaseUrl({
        configuredBaseUrl: "https://api.example.com/",
        platform: "android",
        scriptURL: "http://192.168.1.4:8081/index.bundle?platform=android",
      }),
    ).toBe("https://api.example.com");
  });

  it("infers the Metro host for Expo Go on a real Android device", () => {
    expect(
      resolveApiBaseUrl({
        configuredBaseUrl: "",
        platform: "android",
        scriptURL: "http://192.168.1.4:8081/node_modules/expo/AppEntry.bundle?platform=android",
      }),
    ).toBe("http://192.168.1.4:8001");
  });

  it("falls back to Android emulator localhost only when no host is inferable", () => {
    expect(
      resolveApiBaseUrl({
        configuredBaseUrl: "",
        platform: "android",
        scriptURL: null,
      }),
    ).toBe("http://10.0.2.2:8001");
  });

  it("extracts the Metro host from scriptURL", () => {
    expect(inferDevServerHost("http://192.168.1.4:8081/index.bundle?platform=android")).toBe(
      "192.168.1.4",
    );
  });
});
