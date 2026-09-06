/**
 * /losts was a typo directory. Canonical route is /collection-lots.
 * This page permanently redirects to the canonical URL.
 */
import { redirect } from "next/navigation";

export default function LotsLegacyRedirect() {
  redirect("/collection-lots");
}
