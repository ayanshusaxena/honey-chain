"use client";

import React, { useState } from "react";
import {
  Users,
  ShieldCheck,
  Shield,
  Key,
  UserCheck,
  Search,
  CheckCircle2,
  Lock,
} from "lucide-react";
import { useAppSession } from "../../lib/session-store";
import { AppShell } from "../../components/layout/AppShell";
import { AppHeader } from "../../components/layout/AppHeader";
import { MetricCard } from "../../components/ui/MetricCard";
import { StatusBadge } from "../../components/ui/StatusBadge";
import type { UserRole } from "../../types/contracts";

interface SeededAccount {
  id: string;
  email: string;
  role: UserRole;
  title: string;
  department: string;
  capabilities: string[];
  status: "ACTIVE";
}

const SEEDED_OPERATORS: SeededAccount[] = [
  {
    id: "SEC-USR-001",
    email: "demo.admin@honeychain.local",
    role: "ADMIN",
    title: "Chief Trust & Safety Officer",
    department: "Platform Security & Governance",
    capabilities: [
      "Cryptographic Batch Status Overrides (ACTIVE/HOLD/RECALL)",
      "Hive Lifecycle Provisioning & Decommissioning",
      "Full Multi-Tier Traceability Audit",
      "Blockchain Root Contract Anchoring",
    ],
    status: "ACTIVE",
  },
  {
    id: "SEC-USR-002",
    email: "demo.beekeeper@honeychain.local",
    role: "BEEKEEPER",
    title: "Lead Apiary Beekeeper",
    department: "Field Extraction & Apiary Monitoring",
    capabilities: [
      "Apiary Hive Registration & Maintenance Updates",
      "IoT Sensor Telemetry Transmission",
      "Apiary Harvest Log Registration",
      "Field Hive Allocation Recording",
    ],
    status: "ACTIVE",
  },
  {
    id: "SEC-USR-003",
    email: "demo.processor@honeychain.local",
    role: "PROCESSOR",
    title: "Facility Operations Manager",
    department: "Regional Packaging & Lab Verification",
    capabilities: [
      "Collection Lot Blending & Aggregation",
      "Commercial Processing Batch Bottling",
      "Lab Evidence PDF Certificate Upload",
      "On-Chain Evidence Hash Notarization",
    ],
    status: "ACTIVE",
  },
];

export default function UsersPage() {
  const session = useAppSession();
  const [searchQuery, setSearchQuery] = useState("");

  const filteredOperators = SEEDED_OPERATORS.filter(
    (op) =>
      op.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      op.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      op.department.toLowerCase().includes(searchQuery.toLowerCase()) ||
      op.role.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <AppHeader
          title="Identity & Access Governance"
          breadcrumbs={[
            { label: "Honey Chain", href: "/dashboard" },
            { label: "Management" },
            { label: "Users" },
          ]}
          session={session}
        />

        {/* Active Session Identity Card */}
        <div className="rounded-2xl border border-amber-200/80 bg-gradient-to-r from-amber-500/10 via-amber-500/5 to-transparent p-5 shadow-sm dark:border-amber-900/40 dark:from-amber-950/30 dark:via-amber-950/10">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3.5">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-500 text-white shadow-md shadow-amber-500/20">
                <UserCheck className="h-6 w-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-slate-900 dark:text-white">
                    Active Authenticated Session
                  </h2>
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
                    SECURED
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                  Principal ID: <span className="font-mono font-bold text-slate-700 dark:text-slate-300">{session?.userId ? `${session.userId.slice(0, 8)}...` : "Active Operator"}</span> · Role: <span className="font-bold text-amber-600 dark:text-amber-400">{session?.role || "OPERATOR"}</span>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-300">
              <ShieldCheck className="h-4 w-4 text-emerald-500" />
              <span>JWT Bearer Token Active</span>
            </div>
          </div>
        </div>

        {/* Security Summary Metrics */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="AUTHORIZED ROLES"
            value="3"
            icon={Shield}
            subtitle="ADMIN, BEEKEEPER, PROCESSOR"
          />
          <MetricCard
            title="SEEDED OPERATORS"
            value="3"
            icon={Users}
            subtitle="Cryptographically provisioned"
          />
          <MetricCard
            title="ACCESS CONTROL"
            value="RBAC"
            icon={Lock}
            subtitle="Strict endpoint role gating"
          />
          <MetricCard
            title="KEY MANAGEMENT"
            value="HSM / KMS"
            icon={Key}
            subtitle="Secured secret distribution"
          />
        </div>

        {/* Role Governance & Security Policy Notice */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-[#0c1527]">
          <div className="flex flex-col gap-3 border-b border-slate-100 pb-4 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Platform Operator Role Directory
              </h3>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                Authorized identity profiles and credential specifications configured in the platform security baseline.
              </p>
            </div>

            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Filter operator or role..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8.5 w-full rounded-lg border border-slate-200 bg-slate-50/50 pl-8.5 pr-3 text-xs text-slate-800 placeholder-slate-400 focus:border-amber-500 focus:bg-white focus:outline-none dark:border-slate-700 dark:bg-slate-900/50 dark:text-slate-200 dark:focus:bg-slate-900"
              />
            </div>
          </div>

          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {filteredOperators.map((operator) => (
              <div
                key={operator.id}
                className="p-5 transition-colors hover:bg-slate-50/50 dark:hover:bg-slate-800/30"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="flex items-center gap-2.5">
                      <span className="font-mono text-xs font-bold text-slate-400">
                        {operator.id}
                      </span>
                      <h4 className="text-sm font-bold text-slate-900 dark:text-white">
                        {operator.title}
                      </h4>
                      <StatusBadge status={operator.status} size="sm" />
                    </div>

                    <p className="mt-1 font-mono text-xs font-semibold text-amber-600 dark:text-amber-400">
                      {operator.email}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                      Department: {operator.department}
                    </p>
                  </div>

                  <span className="inline-flex rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-bold text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                    Role: {operator.role}
                  </span>
                </div>

                <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50/50 p-3 text-xs dark:border-slate-800/60 dark:bg-slate-900/40">
                  <span className="font-bold text-slate-600 dark:text-slate-300">
                    Enforced Cryptographic & System Capabilities:
                  </span>
                  <ul className="mt-1.5 grid grid-cols-1 gap-1 sm:grid-cols-2">
                    {operator.capabilities.map((cap, i) => (
                      <li
                        key={i}
                        className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                        <span>{cap}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-slate-100 bg-slate-50/50 p-4 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-400">
            <div className="flex items-center gap-2">
              <Lock className="h-4 w-4 text-slate-400" />
              <span>
                <strong>Security Policy Note:</strong> Platform accounts and asymmetric key pairs are strictly provisioned via identity federation and environment security vaults. Arbitrary in-browser account creation is disallowed by architectural policy.
              </span>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
