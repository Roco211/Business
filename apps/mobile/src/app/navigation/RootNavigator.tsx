import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { NavigationContainer } from "@react-navigation/native";
import { StyleSheet } from "react-native";

import LoginScreen from "../../features/auth/screens/LoginScreen";
import ChatScreen from "../../features/chat/screens/ChatScreen";
import DashboardScreen from "../../features/dashboard/screens/DashboardScreen";
import LedgerScreen from "../../features/ledger/screens/LedgerScreen";
import { AuthProvider, useAuth } from "../../shared/auth/AuthProvider";
import { SessionStreamProvider } from "../../shared/session/SessionStreamProvider";
import { color } from "../../shared/ui";

const Tab = createBottomTabNavigator();

function ProtectedTabs() {
  return (
    <SessionStreamProvider>
      <NavigationContainer>
        <Tab.Navigator
          screenOptions={{
            headerShown: false,
            tabBarActiveTintColor: color.accentPrimary,
            tabBarInactiveTintColor: color.fgTertiary,
            tabBarLabelStyle: styles.tabBarLabel,
            tabBarStyle: styles.tabBar,
          }}
        >
          <Tab.Screen name="\u9996\u9875" component={DashboardScreen} />
          <Tab.Screen name="\u5de5\u4f5c\u53f0" component={ChatScreen} />
          <Tab.Screen name="\u53f0\u8d26" component={LedgerScreen} />
        </Tab.Navigator>
      </NavigationContainer>
    </SessionStreamProvider>
  );
}

function RootNavigatorContent() {
  const auth = useAuth();
  if (!auth.isAuthenticated) {
    return <LoginScreen />;
  }

  return <ProtectedTabs />;
}

export default function RootNavigator() {
  return (
    <AuthProvider>
      <RootNavigatorContent />
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: color.bgSurface,
    borderTopWidth: 0,
    borderRadius: 28,
    bottom: 12,
    elevation: 6,
    height: 72,
    left: 16,
    paddingBottom: 10,
    paddingTop: 10,
    position: "absolute",
    right: 16,
    shadowColor: "#2d211c",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.08,
    shadowRadius: 18,
  },
  tabBarItem: {
    borderRadius: 18,
    marginHorizontal: 4,
  },
  tabBarLabel: {
    fontSize: 12,
    fontWeight: "600",
  },
});
