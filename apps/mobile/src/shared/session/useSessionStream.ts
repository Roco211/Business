import { useContext } from "react";

import { SessionStreamContext } from "./SessionStreamProvider";


export function useSessionStream() {
  return useContext(SessionStreamContext);
}
