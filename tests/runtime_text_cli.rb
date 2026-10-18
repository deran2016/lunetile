module RGSSXP
  DATA_ENCODING = ARGV.fetch(0)
end
load File.expand_path('../src/runtime/text.rb',__dir__)
load File.expand_path('runtime_text.rb',__dir__)
puts "Text normalization #{RGSSXP::DATA_ENCODING}: values, aliases, cycles, frozen keys, native payload/error guards PASS"
