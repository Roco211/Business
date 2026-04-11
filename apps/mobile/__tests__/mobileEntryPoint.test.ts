const mockRegisterRootComponent = jest.fn();

jest.mock("expo/src/launch/registerRootComponent", () => ({
  __esModule: true,
  default: mockRegisterRootComponent,
}));

describe("mobile entry point", () => {
  beforeEach(() => {
    mockRegisterRootComponent.mockClear();
    jest.resetModules();
  });

  test("uses a local index entry file instead of Expo AppEntry", () => {
    const packageJson = require("../package.json");
    let isolatedApp;

    expect(packageJson.main).toBe("./index.js");

    jest.isolateModules(() => {
      isolatedApp = require("../App").default;
      require("../index");
    });

    expect(mockRegisterRootComponent).toHaveBeenCalledTimes(1);
    expect(mockRegisterRootComponent).toHaveBeenCalledWith(isolatedApp);
  });
});
