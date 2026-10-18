# Enumerate public data-class fields, not engine code or game assets.
File.open('types-reference.txt', 'w') do |out|
  visit = nil
  visit = proc do |scope|
    scope.constants.sort.each do |name|
      value = scope.const_get(name)
      next unless value.is_a?(Class)
      fields = value.instance_methods(false).collect {|m| m.to_s}.grep(/=$/).collect {|m| m[0...-1]}.sort
      out.puts(value.name + "\t" + fields.inspect)
      visit.call(value)
    end
  end
  visit.call(RPG)
end
