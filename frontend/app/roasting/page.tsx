import dynamic from "next/dynamic";

const RoastSimulator = dynamic(
  () => import("@/components/roasting/RoastSimulator"),
  {
    ssr: false,
    loading: () => (
      <div className="rounded-lg border border-coffee-200 bg-white p-6 text-coffee-600">
        Loading simulator…
      </div>
    ),
  },
);

const PHASES = [
  {
    name: "Drying",
    range: "charge → ~150°C",
    desc: "Green seeds hold ~10-12% moisture. Heat first boils that water off. The bean stays green-yellow and grassy; almost no flavor has formed yet.",
  },
  {
    name: "Maillard / Browning",
    range: "~150°C → first crack",
    desc: "Sugars and amino acids react (the Maillard reaction) and caramelization begins. The bean turns tan then brown and the roasty, nutty, caramel aromas build.",
  },
  {
    name: "Development",
    range: "first crack → drop",
    desc: "Everything after first crack. Its length — the development-time ratio — decides how far roast flavor overtakes origin character, and so sets the roast level.",
  },
];

const LEVELS = [
  {
    name: "Light",
    examples: "Nordic, Cinnamon",
    desc: "Dropped at or just past first crack. Bright, acidic, tea-like; maximum origin character, no surface oil.",
  },
  {
    name: "Medium-light",
    examples: "City, Omni",
    desc: "Through first crack and a touch beyond. Balanced sweetness with the origin's acidity still in front — the everyday specialty filter roast.",
  },
  {
    name: "Medium",
    examples: "City+",
    desc: "A little more development rounds acidity into caramel sweetness while keeping origin legible.",
  },
  {
    name: "Medium-dark",
    examples: "Full City, Classic Espresso",
    desc: "Developed to the edge of second crack. Bittersweet chocolate and body take over; origin acidity recedes.",
  },
  {
    name: "Dark",
    examples: "Vienna, French, Italian",
    desc: "Into second crack, with oils drawn to a shiny surface. Smoky, carbonized bittersweetness; roast flavor supersedes origin.",
  },
];

export default function RoastingPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-coffee-900">Roasting</h1>
        <p className="mt-1 text-sm text-gray-600">
          Roasting is the one step that turns a hard, grassy green seed into the
          aromatic brown bean we grind. Below: how a roast unfolds, and an
          interactive simulator you can play through.
        </p>
      </header>

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-coffee-900">
          From green seed to roasted bean
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-gray-700">
          A roaster tumbles green seeds in a hot drum for roughly 8–14 minutes.
          Heat drives off water and then triggers the Maillard reaction and
          caramelization — hundreds of new aroma compounds form, the seed loses
          ~15% of its weight, and it nearly doubles in size. Stop early and the
          coffee is bright and acidic; push further and it grows sweet, then
          bittersweet, then smoky.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-coffee-900">
          Reading a roast curve
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-gray-700">
          Roasters track the temperature of a probe buried in the bean mass over
          time. Beans are dropped into a pre-heated drum (the{" "}
          <span className="font-medium text-coffee-800">charge</span>), so the
          probe reads hot, then plunges as the cold beans absorb heat to a{" "}
          <span className="font-medium text-coffee-800">turning point</span>{" "}
          around 90–100°C — the coldest moment of the roast — before climbing
          steadily to the drop. How fast it climbs (the rate of rise) shapes the
          final cup. The chart below is a visual reconstruction from each
          profile&apos;s charge temp, first-crack temp, development ratio, and
          total time — not a captured roaster log.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-coffee-900">The three phases</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {PHASES.map((p) => (
            <div
              key={p.name}
              className="rounded-lg border border-coffee-200 bg-white px-4 py-3"
            >
              <div className="text-sm font-semibold text-coffee-800">{p.name}</div>
              <div className="mt-0.5 text-xs text-coffee-600">{p.range}</div>
              <p className="mt-1.5 text-sm text-gray-600">{p.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-coffee-900">
          First &amp; second crack
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-gray-700">
          <span className="font-medium text-coffee-800">First crack</span>{" "}
          (~196–202°C) is an audible pop as steam pressure splits the bean — the
          start of development and the earliest point the coffee is drinkable.{" "}
          <span className="font-medium text-coffee-800">Second crack</span>{" "}
          (~224°C) is a quieter, snappier crackle reached only by dark roasts; by
          then oils migrate to the surface and the flavor turns smoky and roasty.
          Watch for these markers on the curve.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-coffee-900">
          Roast levels, light to dark
        </h2>
        <div className="mt-3 space-y-2">
          {LEVELS.map((l) => (
            <div
              key={l.name}
              className="rounded-lg border border-coffee-200 bg-white px-4 py-3"
            >
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-sm font-semibold text-coffee-800">
                  {l.name}
                </span>
                <span className="text-xs text-coffee-600">{l.examples}</span>
              </div>
              <p className="mt-1 text-sm text-gray-600">{l.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-coffee-900">Try it</h2>
        <p className="mb-4 mt-2 max-w-3xl text-sm leading-relaxed text-gray-700">
          Pick a roast profile, press play, and watch the bean darken as the
          temperature climbs through each phase. Scrub the timeline to inspect any
          moment, or change the speed.
        </p>
        <RoastSimulator />
      </section>
    </div>
  );
}
