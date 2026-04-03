import { render, screen } from "@testing-library/react-native";

import App from "../App";

test("renders the three primary screen labels", () => {
  render(<App />);

  expect(screen.getAllByText("工作台").length).toBeGreaterThan(0);
  expect(screen.getAllByText("工作群").length).toBeGreaterThan(0);
  expect(screen.getAllByText("账本").length).toBeGreaterThan(0);
});
