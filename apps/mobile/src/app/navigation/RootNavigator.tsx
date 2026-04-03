import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";

import ChatScreen from "../../features/chat/screens/ChatScreen";
import DashboardScreen from "../../features/dashboard/screens/DashboardScreen";
import LedgerScreen from "../../features/ledger/screens/LedgerScreen";

const Tab = createBottomTabNavigator();

export default function RootNavigator() {
  return (
    <NavigationContainer>
      <Tab.Navigator>
        <Tab.Screen name="工作台" component={DashboardScreen} />
        <Tab.Screen name="工作群" component={ChatScreen} />
        <Tab.Screen name="账本" component={LedgerScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
