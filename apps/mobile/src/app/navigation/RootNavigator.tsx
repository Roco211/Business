import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { NavigationContainer } from "@react-navigation/native";

import LoginScreen from "../../features/auth/screens/LoginScreen";
import ChatScreen from "../../features/chat/screens/ChatScreen";
import DashboardScreen from "../../features/dashboard/screens/DashboardScreen";
import LedgerScreen from "../../features/ledger/screens/LedgerScreen";
import { AuthProvider, useAuth } from "../../shared/auth/AuthProvider";
import { SessionStreamProvider } from "../../shared/session/SessionStreamProvider";

const Tab = createBottomTabNavigator();

function ProtectedTabs() {
  return (
    <SessionStreamProvider>
      <NavigationContainer>
        <Tab.Navigator>
          <Tab.Screen name="\u5de5\u4f5c\u53f0" component={DashboardScreen} />
          <Tab.Screen name="\u5de5\u4f5c\u7fa4" component={ChatScreen} />
          <Tab.Screen name="\u8d26\u672c" component={LedgerScreen} />
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
