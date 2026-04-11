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

  it("uses Expo runtime hostUri when SourceCode.scriptURL is unavailable", () => {
    expect(
      resolveApiBaseUrl({
        configuredBaseUrl: "",
        platform: "android",
        scriptURL: null,
        runtimeHostUri: "192.168.1.4:8092",
      }),
    ).toBe("http://192.168.1.4:8001");
  });

  it("uses Android emulator fallback when the inferred host is loopback", () => {
    expect(
      resolveApiBaseUrl({
        configuredBaseUrl: "",
        platform: "android",
        scriptURL: "http://127.0.0.1:8081/index.bundle?platform=android",
      }),
    ).toBe("http://10.0.2.2:8001");

    expect(
      resolveApiBaseUrl({
        configuredBaseUrl: "",
        platform: "android",
        scriptURL: "http://localhost:8081/index.bundle?platform=android",
      }),
    ).toBe("http://10.0.2.2:8001");
  });

  it("extracts the Metro host from scriptURL", () => {
    expect(inferDevServerHost("http://192.168.1.4:8081/index.bundle?platform=android")).toBe(
      "192.168.1.4",
    );
  });

  it("extracts the Metro host from Expo runtime hostUri", () => {
    expect(inferDevServerHost("192.168.1.4:8092")).toBe("192.168.1.4");
  });
});
