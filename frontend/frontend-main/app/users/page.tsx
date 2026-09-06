"use client";

import {
  Users,
  UserPlus,
  ShieldCheck,
  UserRound,
  Search,
  CheckCircle2,
  Clock3,
} from "lucide-react";

type User = {
  id: string;
  name: string;
  email: string;
  role: string;
  status: "ACTIVE" | "PENDING";
};

const users: User[] = [
  {
    id: "USR-001",
    name: "Honey Chain Admin",
    email: "admin@honeychain.com",
    role: "Administrator",
    status: "ACTIVE",
  },
  {
    id: "USR-002",
    name: "Beekeeper A",
    email: "beekeeper.a@honeychain.com",
    role: "Beekeeper",
    status: "ACTIVE",
  },
  {
    id: "USR-003",
    name: "Lab Operator",
    email: "lab@honeychain.com",
    role: "Lab Operator",
    status: "PENDING",
  },
];

export default function UsersPage() {
  return (
    <main className="min-h-screen bg-slate-50 p-5 sm:p-8">

      {/* Header */}
      <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="text-sm font-medium text-amber-600">
            Honey Chain
          </p>

          <div className="mt-1 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
              <Users size={22} />
            </div>

            <h1 className="text-3xl font-bold text-slate-800">
              Users
            </h1>
          </div>

          <p className="mt-2 text-sm text-slate-500">
            Manage platform users and their workspace roles.
          </p>
        </div>

        <button
          onClick={() =>
            alert("User creation form will be connected to the backend.")
          }
          className="flex items-center gap-2 rounded-xl bg-amber-500 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-amber-600"
        >
          <UserPlus size={18} />
          Add User
        </button>
      </div>

      {/* Summary */}
      <div className="mb-7 grid gap-5 sm:grid-cols-3">
        <SummaryCard
          title="Total Users"
          value="3"
          icon={<Users size={21} />}
        />

        <SummaryCard
          title="Active Users"
          value="2"
          icon={<CheckCircle2 size={21} />}
        />

        <SummaryCard
          title="Pending Users"
          value="1"
          icon={<Clock3 size={21} />}
        />
      </div>

      {/* Search */}
      <div className="mb-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <Search size={19} className="text-slate-400" />

          <input
            type="text"
            placeholder="Search users by name or email..."
            className="w-full bg-transparent text-sm text-slate-700 outline-none"
          />
        </div>
      </div>

      {/* User List */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">

        <div className="border-b border-slate-100 p-6">
          <h2 className="text-lg font-bold text-slate-800">
            Platform Users
          </h2>

          <p className="mt-1 text-sm text-slate-400">
            Registered users and assigned roles.
          </p>
        </div>

        <div className="divide-y divide-slate-100">

          {users.map((user) => (
            <div
              key={user.id}
              className="flex flex-col gap-4 p-5 transition hover:bg-slate-50 sm:flex-row sm:items-center sm:justify-between"
            >

              <div className="flex items-center gap-4">

                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
                  <UserRound size={22} />
                </div>

                <div>
                  <p className="font-bold text-slate-700">
                    {user.name}
                  </p>

                  <p className="mt-1 text-sm text-slate-400">
                    {user.email}
                  </p>

                  <p className="mt-1 text-xs text-slate-400">
                    {user.id}
                  </p>
                </div>

              </div>

              <div className="flex items-center gap-3">

                <span className="flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
                  <ShieldCheck size={13} />
                  {user.role}
                </span>

                <span
                  className={`rounded-full px-3 py-1 text-xs font-bold ${
                    user.status === "ACTIVE"
                      ? "bg-green-50 text-green-600"
                      : "bg-yellow-50 text-yellow-600"
                  }`}
                >
                  {user.status}
                </span>

              </div>

            </div>
          ))}

        </div>
      </div>

    </main>
  );
}

function SummaryCard({
  title,
  value,
  icon,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">

      <div className="flex items-center justify-between">

        <div>
          <p className="text-sm font-medium text-slate-400">
            {title}
          </p>

          <h3 className="mt-2 text-3xl font-bold text-slate-800">
            {value}
          </h3>
        </div>

        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
          {icon}
        </div>

      </div>

    </div>
  );
}