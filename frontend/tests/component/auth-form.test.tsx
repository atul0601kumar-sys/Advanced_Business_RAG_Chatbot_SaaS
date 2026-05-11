import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AuthForm } from "@/components/auth-form";

const { push, refresh, login, signup } = vi.hoisted(() => ({
  push: vi.fn(),
  refresh: vi.fn(),
  login: vi.fn(),
  signup: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push,
    refresh,
  }),
}));

vi.mock("@/lib/auth", async () => {
  const actual = await vi.importActual<typeof import("@/lib/auth")>("@/lib/auth");
  return {
    ...actual,
    login,
    signup,
  };
});

test("supports keyboard navigation, submission, and snapshot coverage for signup", async () => {
  const user = userEvent.setup();
  const setItemSpy = vi.spyOn(Storage.prototype, "setItem");
  signup.mockReset();
  push.mockReset();
  refresh.mockReset();
  signup.mockResolvedValueOnce({});

  const { asFragment } = render(<AuthForm mode="signup" />);

  await user.tab();
  expect(screen.getByLabelText("Full name")).toHaveFocus();
  await user.tab();
  expect(screen.getByLabelText("Workspace name")).toHaveFocus();
  await user.tab();
  expect(screen.getByLabelText("Email")).toHaveFocus();
  await user.tab();
  expect(screen.getByLabelText("Password")).toHaveFocus();

  await user.type(screen.getByLabelText("Full name"), "QA User");
  await user.type(screen.getByLabelText("Workspace name"), "Alpha Workspace");
  await user.type(screen.getByLabelText("Email"), "qa@example.com");
  await user.type(screen.getByLabelText("Password"), "CorrectHorseBatteryStaple!");
  await user.click(screen.getByRole("button", { name: "Create account" }));

  await waitFor(() => expect(signup).toHaveBeenCalled());
  expect(setItemSpy).not.toHaveBeenCalled();
  expect(push).toHaveBeenCalledWith("/dashboard");
  expect(refresh).toHaveBeenCalled();
  expect(asFragment()).toMatchSnapshot();
  setItemSpy.mockRestore();
}, 10000);

test("shows accessible error feedback when authentication fails", async () => {
  const user = userEvent.setup();
  login.mockReset();
  login.mockRejectedValueOnce(new Error("Authentication failed."));

  render(<AuthForm mode="login" />);

  await user.type(screen.getByLabelText("Email"), "qa@example.com");
  await user.type(screen.getByLabelText("Password"), "WrongPassword123!");
  await user.click(screen.getByRole("button", { name: "Login" }));

  await screen.findByText("Authentication failed.");
});
