import { useSyncExternalStore } from "react";

export type AuthSession = {
  accessToken: string;
  tokenType: string;
  ownerActorId: string;
  shopId: string;
  shopName: string;
};

type AuthStoreState = {
  session: AuthSession | null;
};

const listeners = new Set<() => void>();

let authStoreState: AuthStoreState = {
  session: null,
};

function emitAuthStoreChange() {
  listeners.forEach((listener) => listener());
}

export function subscribeAuthStore(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getAuthStoreState(): AuthStoreState {
  return authStoreState;
}

export function getAuthSession(): AuthSession | null {
  return authStoreState.session;
}

export function getAccessToken(): string | null {
  return authStoreState.session?.accessToken ?? null;
}

export function setAuthSession(session: AuthSession) {
  authStoreState = { session };
  emitAuthStoreChange();
}

export function clearAuthSession() {
  authStoreState = { session: null };
  emitAuthStoreChange();
}

export function useAuthStoreState() {
  return useSyncExternalStore(subscribeAuthStore, getAuthStoreState, getAuthStoreState);
}
