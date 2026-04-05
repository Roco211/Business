import { useEffect, useState } from "react";
import { Button, ScrollView, Text, TextInput, View } from "react-native";

import { useAuditLogsQuery } from "../hooks/useAuditLogsQuery";
import { useCreateCorrectionMutation } from "../hooks/useCreateCorrectionMutation";
import { useInventoryItemsQuery } from "../hooks/useInventoryItemsQuery";
import { useSessionStream } from "../../../shared/session/useSessionStream";


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
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [selectedItemCurrentStock, setSelectedItemCurrentStock] = useState("");
  const [correctedQuantity, setCorrectedQuantity] = useState("");
  const [correctionReason, setCorrectionReason] = useState("");

  const inventory = useInventoryItemsQuery(searchText);
  const auditLogs = useAuditLogsQuery();
  const correction = useCreateCorrectionMutation();
  const sessionStream = useSessionStream();

  useEffect(() => {
    const eventType = sessionStream.lastEvent?.event_type;
    if (eventType !== "inventory.updated" && eventType !== "confirmation.resolved") {
      return;
    }
    inventory.refresh();
    auditLogs.refresh();
  }, [sessionStream.lastEvent?.event_id]);

  async function handleSubmitCorrection() {
    if (!selectedItemId) {
      return;
    }
    const result = await correction.submitCorrection({
      item_id: selectedItemId,
      expected_quantity: Number(selectedItemCurrentStock),
      corrected_quantity: Number(correctedQuantity),
      reason: correctionReason,
    });
    if (result === null) {
      return;
    }
    setCorrectedQuantity("");
    setCorrectionReason("");
    setSelectedItemId(null);
    setSelectedItemCurrentStock("");
    inventory.refresh();
    auditLogs.refresh();
  }

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
          <Button
            title={`Correct ${item.name}`}
            onPress={() => {
              setSelectedItemId(item.item_id);
              setSelectedItemCurrentStock(item.current_stock);
              setCorrectedQuantity(item.current_stock.replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1"));
              setCorrectionReason("");
            }}
          />
        </View>
      ))}

      {selectedItemId ? (
        <View>
          <Text>Correction form</Text>
          <TextInput
            placeholder="Corrected quantity"
            keyboardType="numeric"
            value={correctedQuantity}
            onChangeText={setCorrectedQuantity}
          />
          <TextInput
            placeholder="Correction reason"
            value={correctionReason}
            onChangeText={setCorrectionReason}
          />
          {correction.error ? <Text>{correction.error}</Text> : null}
          <Button
            title={correction.isSubmitting ? "Submitting..." : "Submit correction"}
            onPress={() => {
              void handleSubmitCorrection();
            }}
            disabled={correction.isSubmitting}
          />
        </View>
      ) : null}

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
