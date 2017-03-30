## Examples

This directory contains examples of tracing applications using the sqlalchemy package. To run the examples, make sure you've installed the packages `opentracing` and `lightstep`. If you have a lightstep token and would like to view the created spans, then uncomment to proper lines under the given examples. If you would like to use a different OpenTracing implementation, you may also replace the lightstep tracer with the tracer of your choice.

Then simply:

```
> python example-file.py
```

