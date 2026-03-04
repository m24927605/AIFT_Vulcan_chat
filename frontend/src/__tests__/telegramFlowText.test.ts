import { describe, expect, it } from "vitest";
import { translations } from "@/i18n/translations";

describe("telegram OTP flow copy", () => {
  it("does not instruct users to fetch Telegram Chat ID", () => {
    expect(translations.en.telegramHint.toLowerCase()).not.toContain("chat id");
    expect(translations["zh-TW"].telegramHint).not.toContain("Chat ID");
  });

  it("mentions one-time link code flow", () => {
    expect(translations.en.telegramHint.toLowerCase()).toContain("link");
    expect(translations["zh-TW"].telegramHint).toContain("驗證碼");
  });
});
