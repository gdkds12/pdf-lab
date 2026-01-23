export function SocialProof() {
  return (
    <section className="self-stretch py-16 flex flex-col justify-center items-center gap-6 overflow-hidden">
      <div className="text-center text-gray-500 text-sm font-medium leading-tight">
        Trusted by top universities
      </div>
      <div className="self-stretch flex justify-center gap-8 md:gap-16 items-center flex-wrap px-6">
         {/* Text Logos instead of Images */}
         {["Seoul Nat'l Univ", "KAIST", "Yonsei Univ", "Korea Univ", "POSTECH"].map((name) => (
             <div key={name} className="text-zinc-600 font-semibold text-xl">{name}</div>
         ))}
      </div>
    </section>
  )
}
