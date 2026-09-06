/**
 * /dashboard/honey-batches was a duplicate batch concept incompatible with
 * the verified backend contract (BatchStatus: ACTIVE | HOLD | RECALL).
 *
 * The authoritative batch route is /batches which uses the correct
 * backend schema. This page redirects there.
 */
import { redirect } from "next/navigation";

export default function HoneyBatchesLegacyRedirect() {
  redirect("/batches");
}
