import { act, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { Pressable, Text } from "react-native";

import RootNavigator from "../../app/navigation/RootNavigator";
import { useLoginMutation } from "../../features/auth/hooks/useLoginMutation";
import { apiGetJson } from "../api/client";
import { AuthProvider, useAuth } from "./AuthProvider";
import { clearAuthSession, setAuthSession } from "./authStore";

jest.mock("../../features/dashboard/screens/DashboardScreen", () => {
  const ReactNative = require("react-native");
  return function MockDashboardScreen() {
    return <ReactNative.Text>Mock Dashboard Screen</ReactNative.Text>;
  };
});

jest.mock("../../features/chat/screens/ChatScreen", () => {
  const ReactNative = require("react-native");
  return function MockChatScreen() {
    return <ReactNative.Text>Mock Chat Screen</ReactNative.Text>;
  };
});

jest.mock("../../features/ledger/screens/LedgerScreen", () => {
  const ReactNative = require("react-native");
  return function MockLedgerScreen() {
    return <ReactNative.Text>Mock Ledger Screen</ReactNative.Text>;
  };
});

jest.mock("../../shared/session/SessionStreamProvider", () => {
  const ReactNative = require("react-native");
  return {
    SessionStreamProvider: ({ children }: { children: React.ReactNode }) => (
      <ReactNative.View testID="session-stream-provider">{children}</ReactNative.View>
    ),
  };
});

describe("AuthProvider", () => {
  function resetAuthStore() {
    act(() => {
      clearAuthSession();
    });
  }

  beforeEach(() => {
    resetAuthStore();
    global.fetch = jest.fn();
  });

  afterEach(() => {
    resetAuthStore();
    jest.resetAllMocks();
  });

  it("starts unauthenticated and updates context when login is called", () => {
    function Consumer() {
      const auth = useAuth();
      return (
        <>
          <Text>{auth.isAuthenticated ? "authenticated" : "anonymous"}</Text>
          <Text>{auth.session?.accessToken ?? "no-token"}</Text>
          <Pressable
            testID="login-context"
            onPress={() =>
              auth.login({
                accessToken: "token_context",
                tokenType: "Bearer",
                ownerActorId: "owner_default",
                shopId: "shop_default",
                shopName: "Demo Shop",
              })
            }
          >
            <Text>Login via context</Text>
          </Pressable>
        </>
      );
    }

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );

    expect(screen.getByText("anonymous")).toBeTruthy();
    expect(screen.getByText("no-token")).toBeTruthy();

    fireEvent.press(screen.getByTestId("login-context"));

    expect(screen.getByText("authenticated")).toBeTruthy();
    expect(screen.getByText("token_context")).toBeTruthy();
  });

  it("stores issued bearer token when login mutation succeeds", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          access_token: "token_from_api",
          token_type: "Bearer",
          owner_actor_id: "owner_default",
          shop_id: "shop_default",
          shop_name: "Demo Shop",
        },
      }),
    });

    function Consumer() {
      const auth = useAuth();
      const login = useLoginMutation();
      return (
        <>
          <Text>{auth.isAuthenticated ? "authenticated" : "anonymous"}</Text>
          <Text>{auth.session?.accessToken ?? "no-token"}</Text>
          <Text>{login.error ?? "no-error"}</Text>
          <Pressable
            testID="login-mutation"
            onPress={() => void login.submitLogin("owner@example.com", "dev-password")}
          >
            <Text>Login via mutation</Text>
          </Pressable>
        </>
      );
    }

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );

    fireEvent.press(screen.getByTestId("login-mutation"));

    await waitFor(() => {
      expect(screen.getByText("authenticated")).toBeTruthy();
      expect(screen.getByText("token_from_api")).toBeTruthy();
    });
  });

  it("preserves raw password bytes when login request is sent", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          access_token: "token_from_api",
          token_type: "Bearer",
          owner_actor_id: "owner_default",
          shop_id: "shop_default",
          shop_name: "Demo Shop",
        },
      }),
    });

    function Consumer() {
      const login = useLoginMutation();
      return (
        <Pressable
          testID="login-mutation-raw-password"
          onPress={() => void login.submitLogin(" owner@example.com ", "  dev-password  ")}
        >
          <Text>Login with raw password</Text>
        </Pressable>
      );
    }

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );

    fireEvent.press(screen.getByTestId("login-mutation-raw-password"));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/login"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            email: "owner@example.com",
            password: "  dev-password  ",
          }),
        }),
      );
    });
  });

  it("shows login screen and blocks protected session bootstrap when signed out", () => {
    render(<RootNavigator />);

    expect(screen.getAllByText("进入门店助理").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("session-stream-provider")).toBeNull();
    expect(screen.queryByText("Mock Dashboard Screen")).toBeNull();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("renders protected navigation when auth session already exists", () => {
    setAuthSession({
      accessToken: "token_existing",
      tokenType: "Bearer",
      ownerActorId: "owner_default",
      shopId: "shop_default",
      shopName: "Demo Shop",
    });

    render(<RootNavigator />);

    expect(screen.getByTestId("session-stream-provider")).toBeTruthy();
    expect(screen.getByText("Mock Dashboard Screen")).toBeTruthy();
  });

  it("returns to login gate when a protected http request gets 401", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({
        error: {
          code: "unauthorized",
          message: "Token expired",
          details: [],
        },
      }),
    });

    act(() => {
      setAuthSession({
        accessToken: "token_expired",
        tokenType: "Bearer",
        ownerActorId: "owner_default",
        shopId: "shop_default",
        shopName: "Demo Shop",
      });
    });

    render(<RootNavigator />);
    expect(screen.getByTestId("session-stream-provider")).toBeTruthy();

    await act(async () => {
      await apiGetJson("/api/v1/dashboard/summary").catch(() => undefined);
    });

    await waitFor(() => {
      expect(screen.getAllByText("进入门店助理").length).toBeGreaterThan(0);
      expect(screen.queryByTestId("session-stream-provider")).toBeNull();
    });
  });
});
