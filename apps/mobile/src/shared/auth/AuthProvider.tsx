import { createContext, useContext } from "react";

import { AuthSession, clearAuthSession, setAuthSession, useAuthStoreState } from "./authStore";

type AuthContextValue = {
  session: AuthSession | null;
  isAuthenticated: boolean;
  login: (session: AuthSession) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const authStoreState = useAuthStoreState();
  const session = authStoreState.session;

  return (
    <AuthContext.Provider
      value={{
        session,
        isAuthenticated: session !== null,
        login: setAuthSession,
        logout: clearAuthSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
