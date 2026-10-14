import { describe, expect, it } from "vitest";
import { call } from "./helpers";

describe("site layout", () => {
  it("wraps every page in the site header and footer", async () => {
    const html = await (await call("/retrouver")).text();
    for (const href of ["/#etapes", "/#exemples", "/#tarif", "/#questions", "/aide", "/essai"]) {
      expect(html).toContain(`href="${href}"`);
    }
    for (const href of ["/mentions-legales", "/cgv", "/confidentialite", "mailto:contact@kaloe.fr"]) {
      expect(html).toContain(`href="${href}"`);
    }
  });
});
