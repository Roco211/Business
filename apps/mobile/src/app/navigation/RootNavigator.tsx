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
import { ROOT_TAB_LABELS, ROOT_TABS, type RootTabParamList } from "./rootTabConfig";

const Tab = createBottomTabNavigator<RootTabParamList>();

function ProtectedTabs() {
  return (
    <SessionStreamProvider>
      <NavigationContainer>
        <Tab.Navigator
          screenOptions={({ route }) => ({
            headerShown: false,
            tabBarShowIcon: false,
            tabBarLabel: ROOT_TAB_LABELS[route.name],
            tabBarLabelStyle: styles.tabBarLabel,
            tabBarStyle: styles.tabBar,
          })}
        >
          <Tab.Screen name={ROOT_TABS.dashboard} component={DashboardScreen} />
          <Tab.Screen name={ROOT_TABS.workbench} component={ChatScreen} />
          <Tab.Screen name={ROOT_TABS.ledger} component={LedgerScreen} />
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
    borderTopColor: color.borderSubtle,
    borderTopWidth: 1,
    elevation: 0,
    shadowOpacity: 0,
  },
  tabBarLabel: {
    color: color.fgSecondary,
    fontSize: 12,
    fontWeight: "600",
  },
});
