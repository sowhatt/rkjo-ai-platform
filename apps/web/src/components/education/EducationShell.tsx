"use client";

import Link from "next/link";
import { ReactNode } from "react";

type EducationSection =
  | "today"
  | "courses"
  | "tutor"
  | "resources"
  | "progress"\n  | "supervision";

type EducationShellProps = {
  active: EducationSection;
  children: ReactNode;
};

const navigation = [
  {
    key: "today" as const,
    href: "/education",
    icon: "⌂",
    label: "Aujourd'hui",
  },
  {
    key: "courses" as const,
    href: "/education/courses",
    icon: "▤",
    label: "Mes cours",
  },
  {
    key: "tutor" as const,
    href: "/education/tutor",
    icon: "✦",
    label: "Professeur IA",
  },
  {
    key: "resources" as const,
    href: "/education/resources",
    icon: "□",
    label: "Ressources",
  },
  {
    key: "progress" as const,
    href: "/education/progress",
    icon: "◫",
    label: "Progression",
  },
];

export default function EducationShell({
  active,
  children,
}: EducationShellProps) {
  return (
    <div className="rkjo-edu-app">
      <aside className="rkjo-edu-side">
        <Link href="/education" className="rkjo-edu-brand">
          <span className="rkjo-edu-mark">R</span>
          <span>
            <strong>RKJO</strong>
            <small>Education</small>
          </span>
        </Link>

        <nav className="rkjo-edu-navigation">
          {navigation.map((item) => (
            <Link
              key={item.key}
              className={
                active === item.key ? "active" : ""
              }
              href={item.href}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="rkjo-edu-profile">
          <span className="rkjo-edu-avatar">RK</span>
          <span>
            <strong>Compte pilote</strong>
            <small>Démo Education</small>
          </span>
        </div>
      </aside>

      <main className="rkjo-edu-content">
        {children}
      </main>

      <nav className="rkjo-mobile-nav">
        {navigation
          .filter((item) => item.key !== "resources")
          .map((item) => (
            <Link
              key={item.key}
              className={
                active === item.key ? "active" : ""
              }
              href={item.href}
            >
              <span>{item.icon}</span>
              {item.key === "today"
                ? "Aujourd'hui"
                : item.key === "courses"
                  ? "Cours"
                  : item.key === "tutor"
                    ? "Professeur"
                    : "Progrès"}
            </Link>
          ))}
      </nav>
    </div>
  );
}
