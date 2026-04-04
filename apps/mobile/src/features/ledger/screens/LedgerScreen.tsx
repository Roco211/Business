import { useState } from "react";
import { ScrollView, Text, TextInput, View } from "react-native";

import { useAuditLogsQuery } from "../hooks/useAuditLogsQuery";
import { useInventoryItemsQuery } from "../hooks/useInventoryItemsQuery";


function formatAuditLine(itemName: string | undefined, quantityDelta: number | undefined) {
  if (!itemName) {
    return "Inventory update";
  }
  if (typeof quantityDelta !== "number") {
    return itemName;
  }
  return `${itemName} +${quantityDelta}`;
}


export default function LedgerScreen() {
  const [searchText, setSearchText] = useState("");
  const inventory = useInventoryItemsQuery(searchText);
  const auditLogs = useAuditLogsQuery();

  if (inventory.isLoading || auditLogs.isLoading) {
    return (
      <View>
        <Text>Loading ledger...</Text>
      </View>
    );
  }

  if (inventory.error || auditLogs.error) {
    return (
      <View>
        <Text>Ledger unavailable</Text>
        <Text>{inventory.error ?? auditLogs.error}</Text>
      </View>
    );
  }

  return (
    <ScrollView>
      <Text>Ledger</Text>
      <TextInput placeholder="Search inventory" value={searchText} onChangeText={setSearchText} />

      <Text>Inventory</Text>
      {inventory.data.length === 0 ? <Text>No inventory items found.</Text> : null}
      {inventory.data.map((item) => (
        <View key={item.item_id}>
          <Text>{item.name}</Text>
          <Text>{`${item.current_stock} ${item.default_unit}`}</Text>
          <Text>{item.current_price ? `Price ${item.current_price}` : "Price unavailable"}</Text>
        </View>
      ))}

      <Text>Recent activity</Text>
      {auditLogs.data.length === 0 ? <Text>No recent activity.</Text> : null}
      {auditLogs.data.map((log) => (
        <View key={log.audit_log_id}>
          <Text>{log.action}</Text>
          <Text>{formatAuditLine(log.metadata.item_name, log.metadata.quantity_delta)}</Text>
          <Text>{log.created_at}</Text>
        </View>
      ))}
    </ScrollView>
  );
}
