# Go Standards — Full Examples Catalogue

Illustrative do/don't code snippets for every rule in the Go standards skill. These are not always complete, runnable programs.

---

## Cosmetic: Braces

```go
// ✅ Compact brace style
tests := []struct{
    name   string
    input  int
    expect string
}{{
    name:  "foo",
    input: 1,
}, {
    name:   "bar",
    input:  2,
    expect: "oh no!",
}}

// ⚠️ Avoid: extra newlines between braces
tests := []struct{
    name   string
    input  int
    expect string
}{
    {
        name:  "foo",
        input: 1,
    },
    {
        name:   "bar",
        input:  2,
        expect: "oh no!",
    },
}
```

## Cosmetic: Spacing

```go
// ✅ Semantic blank lines
x, err := foo()
if err != nil {
    return nil, err
}
print(x)

y := baz()
if y != nil {
    return nil, err
}
return y, nil

// ⚠️ Avoid: aesthetic blank lines
x, err := foo()

if err != nil {
    return nil, err
}

print(x)
y := baz()
if y != nil {
    return nil, err
}

return y, nil
```

## Cosmetic: Grouping

```go
// ✅ Related code grouped together
x := foo()
b := baz()
if b == nil {
    panic("internal error: got nil baz")
}
z := x + b

y := bar()
if y != nil {
    return nil, errors.New("oh no")
}

// ⚠️ Avoid: interleaved unrelated code with unnecessary closure
x := foo()
check := func(x any) any {
    if x == nil {
        panic("internal error: got nil!")
    }
    return x
}
y := bar()
z := x + check(baz())
if y != nil {
    return nil, errors.New("oh no")
}
```

## Error Messages

```go
// ✅ Concise, lowercase, verb-first, context builds up the stack
func checkUrl(url string) error {
    if !strings.HasPrefix(url, "https://") {
        return fmt.Errorf("url %q does not use https", url)
    }
    if len(url) > 256 {
        return fmt.Errorf("url %q is too long", url)
    }
    return nil
}
func checkRequest(url, username, password string) error {
    if err := checkUrl(url); err != nil {
        return fmt.Errorf("request invalid: %v", err)
    }
    return nil
}
// Result: "foo setup failed: request invalid: url "ubuntu.com" does not use https"

// ⚠️ Avoid: capitalised, verbose, redundant context
func checkUrl(url string) error {
    if !strings.HasPrefix(url, "https://") {
        return errors.New("The given url does not use https which is insecure")
    }
}
func checkRequest(url, username, password string) error {
    if err := checkUrl(url); err != nil {
        return fmt.Errorf("Invalid web request: %v", err)
    }
}
// Result: "Library error: Invalid web request: The given url does not use https which is insecure"
```

## Custom Error Types

```go
// ✅ Use fmt.Errorf for unrecoverable errors
func foo() error {
    if err := bar(); err != nil {
        return fmt.Errorf("failed to bar: %v", err)
    }
    return nil
}

// ⚠️ Avoid: custom type for unrecoverable errors
func foo() error {
    if err := bar(); err != nil {
        return someUnrecoverableError{inner: err, reason: "failed to bar"}
    }
    return nil
}
```

## Panic Patterns

```go
// ✅ Foo/MustFoo pair + internal error prefix
func Foo(name string) (string, error) {
    if len(name) > 10 {
        return "", fmt.Errorf("name too long (%d bytes)", len(name))
    }
    return fmt.Sprintf("%q", name), nil
}

func MustFoo(name string) string {
    ret, err := Foo(name)
    if err != nil {
        panic(err)
    }
    return ret
}

func (b *Builder) Grow(n int) {
    if n < 0 {
        panic("internal error: cannot grow buffer by negative amount")
    }
    b.buf = append(b.buf, make([]byte, n)...)
}

// ⚠️ Avoid: panicking where error return is possible, or error where panic fits
func Foo(name string) string {
    if len(name) > 10 {
        panic("string name contains too many bytes")  // should return error
    }
    return fmt.Sprintf("%q", name)
}
```

## Pyramids of Doom

```go
// ✅ Early returns, handler functions
result, err := foo()
if err != nil {
    return nil, err
}
loop:
for {
    select {
    case msg := <-chan1:
        onChan1Msg(msg)
    case msg := <-chan2:
        onChan2Msg(msg)
    case <-done:
        break loop
    }
}

// ⚠️ Avoid: deep nesting
if result, err := foo(); err != nil {
    return nil, err
} else {
    for {
        select {
        case msg := <-chan1:
            if ... {
                // deeply nested handler code
            }
        }
    }
}
```

## Inline If

```go
// ✅ Short expressions inline, long ones broken out
args := Tuple{arg1, arg2}
kvargs := []Tuple{
    {starlark.String("key"), starlark.String("value")},
}
_, err := starlark.Call(thread, myBuiltin, args, kvargs)
if err != nil {
    fmt.Printf("something went wrong: %v\n", err)
}

if err := fn(); err != nil {  // short — fine inline
    fmt.Printf("something went wrong: %v\n", err)
}

// ⚠️ Avoid: long multi-line inline if
if _, err := starlark.Call(
        thread, myBuiltin,
        Tuple{arg1, arg2},
        []Tuple{{starlark.String("key"), starlark.String("value")}}); err != nil {
    fmt.Printf("something went wrong: %v\n", err)
}
```

## Variable Declaration

```go
// ✅ := for most declarations, var when zero value won't be read
count := 0  // zero value may be read before reassignment

var intName string  // will always be assigned before use
if i == 1 {
    intName = "one"
} else {
    intName = "not one"
}

foo := type(expr)  // type assertion via cast, not var foo type = expr
```

## Interface Declaration and Implementation

```go
// ✅ Named parameters aid understanding
type Finder interface {
    Find(haystack, needle string) (x, y int)
}

// ⚠️ Avoid: unnamed parameters
type Finder interface {
    Find(string, string) (int, int)
}

// ✅ Compile-time interface assertion
var _ io.Reader = &MyFile{}
var _ io.Writer = &MyFile{}
```

## Struct Population (Unexported)

```go
// ✅ Named fields, pre-computed values, consistent order
transientAllocs := beforeGCStats.Alloc - afterGCStats.Alloc
nonTransientAllocs := afterGCStats.Alloc - beforeExecStats.Alloc
return measurements{
    totalDuration:      totalDuration,
    transientAllocs:    transientAllocs,
    nonTransientAllocs: nonTransientAllocs,
}

// ⚠️ Avoid: mixed computation, mismatched names, anonymous init
delta := afterGCStats.Alloc - beforeExecStats.Alloc
return measurements{
    totalDuration:      timeTaken,  // name mismatch
    transientAllocs:    beforeGCStats.Alloc - afterGCStats.Alloc,  // mixed inline
    nonTransientAllocs: delta,
}
// or worse:
return measurements{timeTaken, beforeGCStats.Alloc - afterGCStats.Alloc, delta}
```

## Struct Population (Exported)

```go
// ✅ Builder/setter pattern
st := startest.From(t)
st.SetMaxAllocs(100)
st.RequireSafety(starlark.CPUSafe)
st.AddValue("my_value", starlark.String("foo"))

// ⚠️ Avoid: direct struct population exposing internals
st := startest.ST{
    TestBase:       t,
    maxAllocs:      100,
    requiredSafety: starlark.CPUSafe,
    safetyGiven:    true,
}
```

## Function Docs

```go
// ✅ Starts with function name, describes purpose
// Foo transforms the given number into its pretty string representation.
func Foo(i int) string {
    j := baz(i)
    return bar(j)
}

func (foo *Foo) CheckValid() error { ... }

// ⚠️ Avoid: describes implementation, redundant doc
// This function takes an integer, it applies baz to it and then bar and returns the resulting string.
func Foo(i int) string { ... }

// CheckValid checks whether foo is valid.  // redundant
func (foo *Foo) CheckValid() error { ... }
```

## Function Naming

```go
// ✅ Consistent word order
func (foo *Foo) ExecBar() string      { ... }
func (foo *Foo) doBaz() string        { ... }
func (foo *Foo) sqrt(float64) float64 { ... }

// ⚠️ Avoid: inconsistent order, cryptic names
func (foo *Foo) ExecBar() string   { ... }
func (foo *Foo) bazDo() string     { ... }  // reversed word order
func (foo *Foo) f(float64) float64 { ... }  // cryptic
```

## Nil Arguments

```go
// ✅ Document optional nil, don't check non-optional
// PrintFooBar prints Foos and, optionally, Bars.
// If Bar is not required then nil may be passed in its place.
func (baz *Baz) PrintFooBar(foo *Foo, optionalBar *Bar) error {
    fmt.Println(foo.f1)
    if optionalBar != nil {
        fmt.Println(optionalBar)
    }
    return nil
}

// ⚠️ Avoid: defensive nil-checking everything
func (baz *Baz) PrintFooBar(foo *Foo, optionalBar *Bar) error {
    if foo == nil { return fmt.Errorf("foo is nil") }
    if baz == nil { return fmt.Errorf("baz is nil") }
    // ...
}
```

## Passing and Returning Structs

```go
// ✅ Pointer return with nil on error
func measureExecution(fn func() error) (*executionStats, error) {
    if err := fn(); err != nil {
        return nil, err  // clear: no valid result
    }
    return &executionStats{}, nil
}

// ⚠️ Avoid: value return with empty struct on error
func measureExecution(fn func() error) (executionStats, error) {
    if err := fn(); err != nil {
        return executionStats{}, err  // looks like a valid value
    }
}
```

## Return Values

```go
// ✅ Return values directly, zero values on error
func GetBar(name string) (*Bar, error) {
    if bar, ok := knownBars[name]; ok {
        return bar, nil
    }
    return nil, fmt.Errorf("no such bar: %s", name)
}

// ⚠️ Avoid: non-nil value with non-nil error
func GetBar(name string) (*Bar, error) {
    if bar, ok := knownBars[name]; ok {
        return bar, nil
    }
    return &Bar{name: "unknown bar", unknown: true}, fmt.Errorf("no such bar: %s", name)
}
```

## Receivers

```go
// ✅ Always named, consistent pointer type
func (foo *Foo) Bar()  { ... }
func (foo *Foo) Baz()  { ... }
func (foo *Foo) Qux()  { ... }
func (foo *Foo) Quux() { ... }

// ⚠️ Avoid: unnamed, mixed types
func (*Foo) Bar()      { ... }
func (foo Foo) Baz()   { ... }  // value receiver mixed with pointers
func (_ *Foo) Qux()    { ... }
```

## Bare Returns

```go
// ✅ Explicit returns
func (foo *Foo) Get(name string) (value string, err error) {
    switch name {
    case "something special":
        return "some special value", nil
    case "something restricted":
        if !foo.restrictedThingAvailable {
            return "", fmt.Errorf("restricted thing unavailable")
        }
        return "restricted thing", nil
    default:
        return "", fmt.Errorf("unknown key: %q", name)
    }
}

// ⚠️ Avoid: bare return with named values
func (foo *Foo) Get(name string) (value string, err error) {
    switch name {
    case "something special":
        value = "some special value"
    case "something restricted":
        if foo.restrictedThingAvailable {
            value = "restricted thing"
        } else {
            err = fmt.Errorf("restricted thing unavailable")
        }
    default:
        err = fmt.Errorf("unknown key: %q", name)
    }
    return  // unclear what's being returned
}
```

## Table-Driven Tests

```go
func TestIsNil(t *testing.T) {
    tests := []struct{
        name   string
        input  any
        output bool
        expect string
    }{{
        name:   "int",
        input:  123,
        output: false,
    }, {
        name:   "unsafe.Pointer",
        input:  (unsafe.Pointer)(nil),
        output: true,
    }, {
        name:   "func",
        input:  func() {},
        expect: "functions not supported",
    }}
    for _, test := range tests {
        t.Run(test.name, func(t *testing.T) {
            result, err := my_package.IsNil(test.input)
            if err != nil {
                if test.expect == "" {
                    t.Errorf("unexpected error: %v", err)
                } else if err.Error() != test.expect {
                    t.Errorf("incorrect error: expected %q but got %q", test.expect, err)
                }
            }
            if result != test.output {
                t.Errorf("IsNil returned %v", result)
            }
        })
    }
}
```
