import { describe, expect, it } from "vitest";
import { missingPublisherFields, TO_FILL } from "../src/site/legal";
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

describe("/essai", () => {
  it("redirects to the Stripe payment link", async () => {
    const res = await call("/essai", { redirect: "manual" });
    expect(res.status).toBe(302);
    expect(res.headers.get("location")).toBe("https://buy.stripe.test/essai");
  });
});

describe("legal pages", () => {
  it.each([
    ["/mentions-legales", "Mentions légales"],
    ["/cgv", "Conditions générales de vente"],
    ["/confidentialite", "Politique de confidentialité"],
  ])("%s", async (path, title) => {
    const res = await call(path);
    expect(res.status).toBe(200);
    expect(await res.text()).toContain(`<h1>${title}</h1>`);
  });

  it("lists the publisher fields left to fill", () => {
    const filled = { name: "Jeanne Martin", status: "Micro-entreprise", siret: "123", address: "Paris", director: "Jeanne Martin" };
    expect(missingPublisherFields(filled)).toEqual([]);
    expect(missingPublisherFields({ ...filled, siret: TO_FILL, address: TO_FILL })).toEqual(["siret", "address"]);
  });
});
